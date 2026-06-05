package com.retail.product.response;

import java.math.BigDecimal;

public record ProductResponse(
        Integer id,
        String name,
        String description,
        String imageUrl,
        BigDecimal price,
        CategoryResponse category,
        Integer stockQuantity
) {}
