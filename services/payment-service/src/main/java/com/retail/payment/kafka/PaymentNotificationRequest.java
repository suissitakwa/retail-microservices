package com.retail.payment.kafka;

import java.math.BigDecimal;

public record PaymentNotificationRequest(
        Integer orderId,
        Integer customerId,
        String orderReference,
        BigDecimal amount,
        String paymentMethod
) {}
