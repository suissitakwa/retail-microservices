package com.retail.order.kafka;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.util.List;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor
public class OrderEvent {
    private Integer orderId;
    private Integer customerId;
    private BigDecimal amount;
    private List<OrderEventItem> items;
}
