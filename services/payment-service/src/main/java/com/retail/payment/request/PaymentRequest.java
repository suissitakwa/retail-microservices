package com.retail.payment.request;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;

public record PaymentRequest(
        @NotNull Integer orderId,
        @NotNull Integer customerId,
        @NotNull @Positive BigDecimal amount,
        String currency,
        String orderReference,
        String stripeSessionId,
        String customerEmail
) {}
