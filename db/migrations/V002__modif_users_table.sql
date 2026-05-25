-- Create users table for testing Lore analysis

ALTER TABLE users
    MODIFY COLUMN username VARCHAR(30) NOT NULL;

ALTER TABLE users
    ADD COLUMN birthdate date NULL;