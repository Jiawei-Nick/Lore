ALTER TABLE tb_user
    DROP COLUMN legacy_token;

ALTER TABLE tb_user
    DROP COLUMN last_login_v1;

ALTER TABLE tb_user
    ADD COLUMN auth_provider VARCHAR(50) NOT NULL DEFAULT 'local';

ALTER TABLE tb_user
    ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;
