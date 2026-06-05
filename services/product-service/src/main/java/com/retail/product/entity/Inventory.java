package com.retail.product.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.Min;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Getter @Setter
@Builder @NoArgsConstructor @AllArgsConstructor
public class Inventory {

    @Id @GeneratedValue
    private Integer id;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "product_id", nullable = false, unique = true)
    private Product product;

    @Min(value = 0, message = "Stock quantity cannot be negative")
    private Integer quantity;

    private LocalDateTime lastUpdated;
}
