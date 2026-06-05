package com.retail.order.response;

import com.retail.order.enums.OrderStatus;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record OrderResponse(
        Integer id,
        String reference,
        Integer customerId,
        BigDecimal totalAmount,
        OrderStatus status,
        String stripeSessionId,
        List<OrderItemResponse> items,
        LocalDateTime createdDate
) {}
