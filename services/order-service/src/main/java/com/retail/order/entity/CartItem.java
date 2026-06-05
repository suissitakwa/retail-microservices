package com.retail.order.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Getter @Setter
@Builder @NoArgsConstructor @AllArgsConstructor
public class CartItem {

    @Id @GeneratedValue
    private Integer id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "cart_id", nullable = false)
    private Cart cart;

    private Integer productId;
    private String  productName;
    private BigDecimal price;
    private Integer quantity;
}
