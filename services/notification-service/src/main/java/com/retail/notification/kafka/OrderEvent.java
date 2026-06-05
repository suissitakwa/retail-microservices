package com.retail.notification.kafka;

import lombok.*;
import java.math.BigDecimal;
import java.util.List;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor
public class OrderEvent {
    private Integer orderId;
    private Integer customerId;
    private BigDecimal amount;
    private List<OrderEventItem> items;
}
