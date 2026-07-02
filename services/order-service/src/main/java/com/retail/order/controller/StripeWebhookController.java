package com.retail.order.controller;

import com.retail.order.service.OrderService;
import com.stripe.exception.EventDataObjectDeserializationException;
import com.stripe.model.Event;
import com.stripe.model.EventDataObjectDeserializer;
import com.stripe.model.PaymentIntent;
import com.stripe.model.checkout.Session;
import com.stripe.net.Webhook;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Receives Stripe webhooks directly, so the microservices stack can process a full
 * checkout-to-paid flow standalone, without depending on the monolith's webhook handler.
 */
@RestController
@RequestMapping("/api/v1/orders/stripe")
@RequiredArgsConstructor
@Slf4j
public class StripeWebhookController {

    private final OrderService orderService;

    @Value("${stripe.webhook.secret}")
    private String webhookSecret;

    @PostMapping("/webhook")
    public ResponseEntity<String> handleWebhook(
            @RequestBody String payload,
            @RequestHeader("Stripe-Signature") String signature) {

        Event event;
        try {
            event = Webhook.constructEvent(payload, signature, webhookSecret);
        } catch (Exception e) {
            log.warn("Invalid Stripe signature: {}", e.getMessage());
            return ResponseEntity.badRequest().body("Invalid signature");
        }

        log.info("Received Stripe event: {}", event.getType());

        EventDataObjectDeserializer deserializer = event.getDataObjectDeserializer();
        Object data;
        try {
            data = deserializer.deserializeUnsafe();
        } catch (EventDataObjectDeserializationException e) {
            log.warn("Deserialization error: {}", e.getMessage());
            return ResponseEntity.ok("Ignored");
        }

        switch (event.getType()) {
            case "checkout.session.completed" -> {
                Session session = (Session) data;
                orderService.attachPaymentIntent(session.getId(), session.getPaymentIntent());

                // Handle race: payment_intent.succeeded may arrive before this event.
                if ("paid".equals(session.getPaymentStatus())) {
                    orderService.markCompleted(session.getPaymentIntent());
                }
            }
            case "payment_intent.succeeded" -> {
                PaymentIntent pi = (PaymentIntent) data;
                orderService.markCompleted(pi.getId());
            }
            default -> log.debug("Ignored event type: {}", event.getType());
        }

        return ResponseEntity.ok("Processed");
    }
}
