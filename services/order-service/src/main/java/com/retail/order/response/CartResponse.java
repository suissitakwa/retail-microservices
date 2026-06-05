package com.retail.order.response;

import java.math.BigDecimal;
import java.util.List;

public record CartResponse(
        Integer id,
        Integer customerId,
        List<CartItemResponse> items,
        BigDecimal total
) {}
