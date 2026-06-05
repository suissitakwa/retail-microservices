package com.retail.notification.kafka;

import com.retail.notification.entity.Notification;
import com.retail.notification.repository.NotificationRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class NotificationConsumer {

    private final NotificationRepository notificationRepository;

    @KafkaListener(topics = "order.created", groupId = "notification-service")
    @Transactional
    public void onOrderCreated(OrderEvent event) {
        log.info("Received order.created for orderId={}", event.getOrderId());
        String reference = "ORD-" + event.getOrderId();
        Notification notification = Notification.builder()
                .type("ORDER_PLACED")
                .message("Your order #" + reference + " has been placed successfully.")
                .customerId(event.getCustomerId())
                .orderId(event.getOrderId())
                .orderReference(reference)
                .isRead(false)
                .build();
        notificationRepository.save(notification);
    }

    @KafkaListener(topics = "payment.processed", groupId = "notification-service")
    @Transactional
    public void onPaymentProcessed(PaymentNotificationRequest event) {
        log.info("Received payment.processed for orderId={}", event.getOrderId());
        String ref = event.getOrderReference() != null ? event.getOrderReference() : "ORD-" + event.getOrderId();
        String message = String.format(
                "Payment confirmed for order #%s. Amount: $%s", ref, event.getAmount());
        Notification notification = Notification.builder()
                .type("PAYMENT_PAID")
                .message(message)
                .customerId(event.getCustomerId())
                .orderId(event.getOrderId())
                .orderReference(ref)
                .isRead(false)
                .build();
        notificationRepository.save(notification);
    }
}
