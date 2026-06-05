package com.retail.order.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Getter @Setter
@Builder @NoArgsConstructor @AllArgsConstructor
public class OrderItem {

    @Id @GeneratedValue
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    private Integer productId;
    private String  productName;
    private BigDecimal price;
    private Integer quantity;
}
