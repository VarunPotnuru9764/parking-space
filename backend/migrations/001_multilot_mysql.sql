-- One-time additive migration for MySQL. Take and verify a database backup first.
-- Run against the configured database before starting the updated API.
-- All pre-existing parking spaces, histories and fare rules are assigned to the
-- Simulator lot so their meaning and IDs remain unchanged.

CREATE TABLE IF NOT EXISTS parking_lots (
    lot_id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(80) NOT NULL,
    location VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lot_id),
    UNIQUE KEY uq_parking_lots_name (name),
    UNIQUE KEY uq_parking_lots_slug (slug)
) ENGINE=InnoDB;

INSERT INTO parking_lots (name, slug, location)
SELECT 'Simulator', 'simulator', 'Existing simulator data'
WHERE NOT EXISTS (SELECT 1 FROM parking_lots WHERE slug = 'simulator');

ALTER TABLE parking_records ADD COLUMN lot_id INT NULL;
UPDATE parking_records
SET lot_id = (SELECT lot_id FROM parking_lots WHERE slug = 'simulator')
WHERE lot_id IS NULL;
ALTER TABLE parking_records MODIFY lot_id INT NOT NULL;

ALTER TABLE fare_rules ADD COLUMN lot_id INT NULL;
UPDATE fare_rules
SET lot_id = (SELECT lot_id FROM parking_lots WHERE slug = 'simulator')
WHERE lot_id IS NULL;
ALTER TABLE fare_rules MODIFY lot_id INT NOT NULL;

ALTER TABLE parking_history ADD COLUMN lot_id INT NULL;
UPDATE parking_history h
JOIN parking_records p ON p.parking_id = h.parking_id
SET h.lot_id = p.lot_id
WHERE h.lot_id IS NULL;
ALTER TABLE parking_history MODIFY lot_id INT NOT NULL;

ALTER TABLE fare_history ADD COLUMN lot_id INT NULL;
UPDATE fare_history f
JOIN parking_history h ON h.history_id = f.history_id
SET f.lot_id = h.lot_id
WHERE f.lot_id IS NULL;
ALTER TABLE fare_history MODIFY lot_id INT NOT NULL;

ALTER TABLE parking_records
    ADD CONSTRAINT fk_parking_records_lot FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id),
    ADD KEY ix_parking_records_lot_id (lot_id);
ALTER TABLE fare_rules
    ADD CONSTRAINT fk_fare_rules_lot FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id),
    ADD KEY ix_fare_rules_lot_id (lot_id);
ALTER TABLE parking_history
    ADD CONSTRAINT fk_parking_history_lot FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id),
    ADD KEY ix_parking_history_lot_id (lot_id);
ALTER TABLE fare_history
    ADD CONSTRAINT fk_fare_history_lot FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id),
    ADD KEY ix_fare_history_lot_id (lot_id);

-- Before this statement, inspect SHOW INDEX FROM parking_records and drop the
-- old UNIQUE index on slot_number (its generated name may vary by DB version):
-- ALTER TABLE parking_records DROP INDEX <existing_unique_slot_number_index>;
ALTER TABLE parking_records DROP INDEX slot_number;
ALTER TABLE parking_records
    ADD CONSTRAINT uq_parking_lot_slot UNIQUE (lot_id, slot_number);
