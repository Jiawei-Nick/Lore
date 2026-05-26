ALTER TABLE tb_order_header
    DROP COLUMN legacy_ref_code;

ALTER TABLE tb_payment
    DROP COLUMN old_gateway_id;

ALTER TABLE tb_product
    DROP COLUMN discontinued_flag;
