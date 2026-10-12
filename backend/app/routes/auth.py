import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import SECRET_KEY, create_access_token, get_current_user, hash_password, verify_password
from app.config import get_setting
from app.database import get_db
from app.models.audit import EmailChallenge, PasswordResetToken, UserSecurity
from app.models.users import User
from app.schemas.admin import (
    MfaDisable,
    MfaLoginVerify,
    MfaResend,
    PasswordResetComplete,
    PasswordResetRequest,
)
from app.schemas.auth import UserLogin, UserRegister
from app.services.audit import record_event
from app.services.mailer import email_delivery_configuration, send_account_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
OTP_LIFETIME = timedelta(minutes=5)
PASSWORD_RESET_LIFETIME = timedelta(minutes=30)
OTP_RESEND_INTERVAL = timedelta(seconds=30)
MAX_OTP_ATTEMPTS = 5
RESET_REQUEST_RESPONSE = {
    "message": "If an account exists and email delivery succeeds, password reset instructions will be sent. This endpoint does not disclose whether the account exists."
}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _code_hash(user_id: int, code: str) -> str:
    value = f"ParkingSpace:{user_id}:{code}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), value, hashlib.sha256).hexdigest()


def _send_code(user: User, code: str, purpose: str) -> None:
    action = {"mfa_setup": "enable two-step verification", "mfa_disable": "disable two-step verification"}.get(purpose, "sign in")
    subject = "Your ParkingSpace verification code"
    send_account_email(
        user.email,
        subject,
        f"Your ParkingSpace code is {code}. It expires in 5 minutes. Use this code to {action}. If you did not request it, ignore this message.",
    )


def _new_challenge(db: Session, user: User, purpose: str) -> tuple[EmailChallenge, str, str]:
    token = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailChallenge(
        user_id=user.user_id,
        purpose=purpose,
        token_hash=_token_hash(token),
        code_hash=_code_hash(user.user_id, code),
        expires_at=datetime.utcnow() + OTP_LIFETIME,
        attempts=0,
        last_sent_at=datetime.utcnow(),
    )
    db.add(challenge)
    db.flush()
    return challenge, token, code


def _check_challenge(challenge: EmailChallenge | None, expected_purpose: str) -> EmailChallenge:
    now = datetime.utcnow()
    if challenge is None or challenge.purpose != expected_purpose:
        raise HTTPException(status_code=400, detail="Invalid verification challenge")
    if challenge.consumed_at is not None:
        raise HTTPException(status_code=400, detail="This verification challenge has already been used")
    if challenge.expires_at <= now:
        raise HTTPException(status_code=400, detail="The verification code has expired")
    if challenge.attempts >= MAX_OTP_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many incorrect verification attempts")
    return challenge


def _verify_code(challenge: EmailChallenge, code: str) -> bool:
    return secrets.compare_digest(
        challenge.code_hash or "",
        _code_hash(challenge.user_id, code),
    )


def _audit_login(db: Session, request: Request, user: User | None, email: str, success: bool, description: str = "") -> None:
    record_event(
        db,
        request,
        "login.success" if success else "login.failed",
        description or ("Successful login." if success else "Failed login attempt."),
        actor_user_id=user.user_id if user else None,
        email=email[:150],
        success=success,
    )


@router.post("/register", status_code=201)
def register_user(user: UserRegister, request: Request, db: Session = Depends(get_db)):
    new_user = User(
        name=user.name.strip(),
        email=user.email.strip().lower(),
        password_hash=hash_password(user.password),
        role="user",
    )
    try:
        db.add(new_user)
        db.flush()
        record_event(db, request, "account.registered", "User account registered.", new_user.user_id, new_user.email)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email already exists") from exc
    return {"message": "User registered successfully", "user_id": new_user.user_id}


@router.post("/login", status_code=200)
def login_user(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    email = user.email.strip().lower()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user is None or not verify_password(user.password, existing_user.password_hash):
        _audit_login(db, request, existing_user, email, False)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    security = db.query(UserSecurity).filter(UserSecurity.user_id == existing_user.user_id).first()
    if security is not None and security.mfa_enabled:
        now = datetime.utcnow()
        recent_challenge = db.query(EmailChallenge).filter(
            EmailChallenge.user_id == existing_user.user_id,
            EmailChallenge.purpose == "mfa_login",
            EmailChallenge.consumed_at.is_(None),
            EmailChallenge.last_sent_at > now - OTP_RESEND_INTERVAL,
        ).first()
        if recent_challenge is not None:
            raise HTTPException(status_code=429, detail="A verification code was sent recently. Wait before requesting another.")
        for old in db.query(EmailChallenge).filter(
            EmailChallenge.user_id == existing_user.user_id,
            EmailChallenge.purpose == "mfa_login",
            EmailChallenge.consumed_at.is_(None),
        ).all():
            old.consumed_at = now
        challenge: EmailChallenge | None = None
        try:
            challenge, token, code = _new_challenge(db, existing_user, "mfa_login")
            db.commit()
            _send_code(existing_user, code, "mfa_login")
        except RuntimeError as exc:
            db.rollback()
            if challenge is not None:
                challenge.consumed_at = datetime.utcnow()
                db.commit()
            record_event(db, request, "login.mfa_delivery_failed", "Multi-factor code delivery is not configured or failed.", existing_user.user_id, email, False)
            db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "mfa_required": True,
            "challenge_token": token,
            "expires_in": int(OTP_LIFETIME.total_seconds()),
            "resend_after": int(OTP_RESEND_INTERVAL.total_seconds()),
        }

    _audit_login(db, request, existing_user, email, True)
    db.commit()
    access_token = create_access_token(existing_user.user_id, existing_user.role)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/mfa/verify")
def verify_login_mfa(payload: MfaLoginVerify, request: Request, db: Session = Depends(get_db)):
    challenge = _check_challenge(db.query(EmailChallenge).filter(EmailChallenge.token_hash == _token_hash(payload.challenge_token)).first(), "mfa_login")
    user = db.query(User).filter(User.user_id == challenge.user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate verification challenge")
    if not _verify_code(challenge, payload.code):
        challenge.attempts += 1
        record_event(db, request, "login.failed", "Invalid multi-factor verification code.", user.user_id, user.email, False)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid verification code")
    challenge.consumed_at = datetime.utcnow()
    _audit_login(db, request, user, user.email, True, "Successful login with two-step verification.")
    db.commit()
    return {"access_token": create_access_token(user.user_id, user.role), "token_type": "bearer"}


@router.post("/mfa/resend")
def resend_login_mfa(payload: MfaResend, request: Request, db: Session = Depends(get_db)):
    challenge = _check_challenge(db.query(EmailChallenge).filter(EmailChallenge.token_hash == _token_hash(payload.challenge_token)).first(), "mfa_login")
    now = datetime.utcnow()
    if challenge.last_sent_at and now - challenge.last_sent_at < OTP_RESEND_INTERVAL:
        wait = int((OTP_RESEND_INTERVAL - (now - challenge.last_sent_at)).total_seconds())
        raise HTTPException(status_code=429, detail=f"Wait {max(wait, 1)} seconds before requesting another code")
    user = db.query(User).filter(User.user_id == challenge.user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate verification challenge")
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge.code_hash = _code_hash(user.user_id, code)
    challenge.expires_at = now + OTP_LIFETIME
    challenge.last_sent_at = now
    challenge.attempts = 0
    db.commit()
    try:
        _send_code(user, code, "mfa_login")
    except RuntimeError as exc:
        record_event(db, request, "login.mfa_delivery_failed", "Resent multi-factor code could not be delivered.", user.user_id, user.email, False)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "A new verification code has been sent.", "expires_in": int(OTP_LIFETIME.total_seconds())}


@router.post("/mfa/setup")
def start_mfa_setup(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    security = db.query(UserSecurity).filter(UserSecurity.user_id == current_user.user_id).first()
    if security and security.mfa_enabled:
        raise HTTPException(status_code=409, detail="Two-step verification is already enabled")
    for old in db.query(EmailChallenge).filter(
        EmailChallenge.user_id == current_user.user_id,
        EmailChallenge.purpose == "mfa_setup",
        EmailChallenge.consumed_at.is_(None),
    ).all():
        old.consumed_at = datetime.utcnow()
    challenge, token, code = _new_challenge(db, current_user, "mfa_setup")
    db.commit()
    try:
        _send_code(current_user, code, "mfa_setup")
    except RuntimeError as exc:
        challenge.consumed_at = datetime.utcnow()
        record_event(db, request, "security.mfa_setup_delivery_failed", "Two-step verification setup code could not be delivered.", current_user.user_id, current_user.email, False)
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "A verification code has been sent to your account email.", "challenge_token": token, "expires_in": int(OTP_LIFETIME.total_seconds())}


@router.post("/mfa/enable")
def enable_mfa(
    payload: MfaLoginVerify,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    challenge = db.query(EmailChallenge).filter(
        EmailChallenge.token_hash == _token_hash(payload.challenge_token),
        EmailChallenge.user_id == current_user.user_id,
    ).first()
    challenge = _check_challenge(challenge, "mfa_setup")
    if not _verify_code(challenge, payload.code):
        challenge.attempts += 1
        record_event(db, request, "security.mfa_enable_failed", "Invalid code while enabling two-step verification.", current_user.user_id, current_user.email, False)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")
    security = db.query(UserSecurity).filter(UserSecurity.user_id == current_user.user_id).first()
    if security is None:
        security = UserSecurity(user_id=current_user.user_id, mfa_enabled=True)
        db.add(security)
    else:
        security.mfa_enabled = True
    challenge.consumed_at = datetime.utcnow()
    record_event(db, request, "security.mfa_enabled", "Two-step verification enabled.", current_user.user_id, current_user.email)
    db.commit()
    return {"message": "Two-step verification enabled", "mfa_enabled": True}


@router.post("/mfa/disable/request")
def request_mfa_disable(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    security = db.query(UserSecurity).filter(UserSecurity.user_id == current_user.user_id).first()
    if security is None or not security.mfa_enabled:
        raise HTTPException(status_code=409, detail="Two-step verification is not enabled")
    for old in db.query(EmailChallenge).filter(
        EmailChallenge.user_id == current_user.user_id,
        EmailChallenge.purpose == "mfa_disable",
        EmailChallenge.consumed_at.is_(None),
    ).all():
        old.consumed_at = datetime.utcnow()
    _, token, code = _new_challenge(db, current_user, "mfa_disable")
    db.commit()
    try:
        _send_code(current_user, code, "mfa_disable")
    except RuntimeError as exc:
        challenge = db.query(EmailChallenge).filter(EmailChallenge.token_hash == _token_hash(token)).first()
        if challenge:
            challenge.consumed_at = datetime.utcnow()
            record_event(db, request, "security.mfa_disable_delivery_failed", "Two-step verification disable code could not be delivered.", current_user.user_id, current_user.email, False)
            db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "A verification code has been sent to your account email.", "challenge_token": token, "expires_in": int(OTP_LIFETIME.total_seconds())}


@router.delete("/mfa")
def confirm_mfa_disable(
    payload: MfaDisable,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    challenge = _check_challenge(db.query(EmailChallenge).filter(
        EmailChallenge.token_hash == _token_hash(payload.challenge_token),
        EmailChallenge.user_id == current_user.user_id,
    ).first(), "mfa_disable")
    if not _verify_code(challenge, payload.code):
        challenge.attempts += 1
        record_event(db, request, "security.mfa_disable_failed", "Invalid code while disabling two-step verification.", current_user.user_id, current_user.email, False)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")
    security = db.query(UserSecurity).filter(UserSecurity.user_id == current_user.user_id).first()
    if security is not None:
        security.mfa_enabled = False
    challenge.consumed_at = datetime.utcnow()
    record_event(db, request, "security.mfa_disabled", "Two-step verification disabled.", current_user.user_id, current_user.email)
    db.commit()
    return {"message": "Two-step verification disabled", "mfa_enabled": False}


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    try:
        email_delivery_configuration()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return RESET_REQUEST_RESPONSE
    now = datetime.utcnow()
    recent_request = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.user_id,
        PasswordResetToken.created_at > now - OTP_RESEND_INTERVAL,
    ).first()
    if recent_request is not None:
        return RESET_REQUEST_RESPONSE
    token = secrets.token_urlsafe(32)
    reset = PasswordResetToken(
        user_id=user.user_id,
        token_hash=_token_hash(token),
        expires_at=now + PASSWORD_RESET_LIFETIME,
        created_at=now,
    )
    db.add(reset)
    db.commit()
    frontend_url = get_setting("FRONTEND_URL", "http://localhost:5173/#/reset-password")
    reset_url = f"{frontend_url}?token={token}"
    try:
        send_account_email(
            user.email,
            "Reset your ParkingSpace password",
            f"Use this link within 30 minutes to reset your password:\n\n{reset_url}\n\nIf you did not request a password reset, ignore this email.",
        )
    except RuntimeError:
        reset.consumed_at = datetime.utcnow()
        record_event(db, request, "account.password_reset_delivery_failed", "Password reset email delivery failed.", user.user_id, user.email, False)
        db.commit()
        return RESET_REQUEST_RESPONSE
    record_event(db, request, "account.password_reset_requested", "Password reset email sent.", user.user_id, user.email)
    db.commit()
    return RESET_REQUEST_RESPONSE


@router.post("/password-reset/complete")
def complete_password_reset(payload: PasswordResetComplete, request: Request, db: Session = Depends(get_db)):
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == _token_hash(payload.token)).first()
    now = datetime.utcnow()
    if reset is None or reset.consumed_at is not None or reset.expires_at <= now:
        raise HTTPException(status_code=400, detail="Password reset link is invalid, expired, or already used")
    user = db.query(User).filter(User.user_id == reset.user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Password reset link is invalid, expired, or already used")
    user.password_hash = hash_password(payload.new_password)
    reset.consumed_at = now
    for other in db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.user_id,
        PasswordResetToken.reset_id != reset.reset_id,
        PasswordResetToken.consumed_at.is_(None),
    ).all():
        other.consumed_at = now
    for challenge in db.query(EmailChallenge).filter(
        EmailChallenge.user_id == user.user_id,
        EmailChallenge.consumed_at.is_(None),
    ).all():
        challenge.consumed_at = now
    record_event(db, request, "account.password_reset_completed", "Password reset completed.", user.user_id, user.email)
    db.commit()
    return {"message": "Password reset successfully"}


@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    security = db.query(UserSecurity).filter(UserSecurity.user_id == current_user.user_id).first()
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at,
        "mfa_enabled": bool(security and security.mfa_enabled),
    }
