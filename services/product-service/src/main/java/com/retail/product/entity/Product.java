package com.retail.product.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Getter @Setter
@Builder @NoArgsConstructor @AllArgsConstructor
public class Product {

    @Id @GeneratedValue
    private Integer id;
    private String name;
    private String description;

    @Column(name = "image_url")
    private String imageUrl;

    private BigDecimal price;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "category_id")
    private Category category;

    @OneToOne(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private Inventory inventory;
}
