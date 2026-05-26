ALTER TABLE tb_payment
    ADD COLUMN gateway_ref VARCHAR(200) NULL;

ALTER TABLE tb_payment
    ADD COLUMN paid_at TIMESTAMP NULL;

ALTER TABLE tb_payment
    ADD COLUMN failure_reason VARCHAR(500) NULL;

ALTER TABLE tb_order_header
    ADD COLUMN payment_id BIGINT NULL;

CREATE INDEX idx_payment_gateway_ref ON tb_payment(gateway_ref);
