package com.retail.notification.kafka;

import lombok.*;

@Getter @Setter @NoArgsConstructor @AllArgsConstructor
public class OrderEventItem {
    private Integer productId;
    private Integer quantity;
}
