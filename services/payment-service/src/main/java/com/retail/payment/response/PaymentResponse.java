package com.retail.payment.response;

import com.retail.payment.enums.PaymentStatus;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record PaymentResponse(
        Integer id,
        Integer orderId,
        Integer customerId,
        BigDecimal amount,
        String currency,
        PaymentStatus status,
        String orderReference,
        String stripeSessionId,
        String stripePaymentIntentId,
        LocalDateTime createdAt
) {}
