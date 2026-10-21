package com.retail.order.response;

import com.retail.order.enums.OrderStatus;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/** Admin view of an order, including the Stripe intent ID and last-modified time needed for reconciliation. */
public record AdminOrderResponse(
        Integer id,
        String reference,
        Integer customerId,
        BigDecimal totalAmount,
        OrderStatus status,
        String stripeSessionId,
        String stripePaymentIntentId,
        List<OrderItemResponse> items,
        LocalDateTime createdDate,
        LocalDateTime lastModifiedDate
) {}
