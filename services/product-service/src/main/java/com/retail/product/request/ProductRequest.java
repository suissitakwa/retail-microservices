package com.retail.product.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;

public record ProductRequest(
        @NotBlank String name,
        String description,
        String imageUrl,
        @NotNull @Positive BigDecimal price,
        @NotNull Integer categoryId
) {}
