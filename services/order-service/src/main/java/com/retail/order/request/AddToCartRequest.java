package com.retail.order.request;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record AddToCartRequest(
        @NotNull Integer productId,
        @NotNull @Min(1) Integer quantity
) {}
