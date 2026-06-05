package com.retail.order.kafka;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class OrderProducer {

    private static final String TOPIC = "order.created";
    private final KafkaTemplate<String, OrderEvent> kafkaTemplate;

    public void sendOrderCreatedEvent(OrderEvent event) {
        log.info("Publishing order.created for orderId={}", event.getOrderId());
        kafkaTemplate.send(TOPIC, event);
    }
}
