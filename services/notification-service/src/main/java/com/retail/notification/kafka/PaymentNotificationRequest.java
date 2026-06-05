package com.retail.notification.kafka;

import lombok.*;
import java.math.BigDecimal;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor
public class PaymentNotificationRequest {
    private Integer orderId;
    private Integer customerId;
    private String  orderReference;
    private BigDecimal amount;
    private String  paymentMethod;
}
