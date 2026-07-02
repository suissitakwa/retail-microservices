package com.retail.order.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
import java.util.Map;

/**
 * Thin HTTP client to payment-service.
 * Lets order-service create and confirm payments directly, so the microservices
 * stack can process a full checkout-to-paid flow without depending on the monolith.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class PaymentClient {

    private final RestClient restClient;

    @Value("${payment-service.url:http://localhost:8082}")
    private String paymentServiceUrl;

    public void createPayment(Integer orderId, Integer customerId, BigDecimal amount,
                               String orderReference, String stripeSessionId, String customerEmail) {
        try {
            restClient.post()
                    .uri(paymentServiceUrl + "/api/v1/payments")
                    .body(Map.of(
                            "orderId", orderId,
                            "customerId", customerId,
                            "amount", amount,
                            "currency", "usd",
                            "orderReference", orderReference,
                            "stripeSessionId", stripeSessionId,
                            "customerEmail", customerEmail == null ? "" : customerEmail
                    ))
                    .retrieve()
                    .toBodilessEntity();
        } catch (Exception e) {
            log.warn("Failed to create PENDING payment for order {}: {}", orderId, e.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    public Integer findPaymentIdByOrderId(Integer orderId) {
        try {
            Map<String, Object> response = restClient.get()
                    .uri(paymentServiceUrl + "/api/v1/payments/order/" + orderId)
                    .retrieve()
                    .body(Map.class);
            return response != null ? (Integer) response.get("id") : null;
        } catch (Exception e) {
            log.warn("Failed to look up payment for order {}: {}", orderId, e.getMessage());
            return null;
        }
    }

    public void confirmPayment(Integer paymentId, String stripePaymentIntentId) {
        try {
            restClient.patch()
                    .uri(paymentServiceUrl + "/api/v1/payments/" + paymentId + "/confirm?stripePaymentIntentId=" + stripePaymentIntentId)
                    .retrieve()
                    .toBodilessEntity();
        } catch (Exception e) {
            log.warn("Failed to confirm payment {}: {}", paymentId, e.getMessage());
        }
    }
}
