ALTER TABLE tb_order_header
    DROP COLUMN notes;

ALTER TABLE tb_order_item
    ADD COLUMN discount_pct DECIMAL(5,2) NULL DEFAULT 0.00;
