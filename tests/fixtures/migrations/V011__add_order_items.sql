CREATE TABLE tb_order_item (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(18,2) NOT NULL
);

ALTER TABLE tb_order_header
    ADD COLUMN notes VARCHAR(500) NULL;
