package com.retail.order.response;

import java.math.BigDecimal;

public record CartItemResponse(
        Integer id,
        Integer productId,
        String productName,
        BigDecimal price,
        Integer quantity
) {}
