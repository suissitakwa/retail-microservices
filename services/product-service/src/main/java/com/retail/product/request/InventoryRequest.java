package com.retail.product.request;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record InventoryRequest(
        @NotNull Integer productId,
        @NotNull @Min(0) Integer quantity
) {}
