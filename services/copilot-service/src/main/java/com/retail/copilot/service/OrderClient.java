package com.retail.copilot.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Component
@RequiredArgsConstructor
@Slf4j
public class OrderClient {

    private final RestClient restClient;

    @Value("${order-service.url:http://localhost:8085}")
    private String orderServiceUrl;

    @SuppressWarnings("unchecked")
    public Map<String, Object> getOrder(Integer orderId, String bearerToken) {
        log.info("Fetching order {} from order-service", orderId);
        return restClient.get()
                .uri(orderServiceUrl + "/api/v1/orders/my-orders/" + orderId)
                .header("Authorization", bearerToken)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getMyOrders(int limit, String bearerToken) {
        log.info("Fetching up to {} recent orders from order-service", limit);
        return restClient.get()
                .uri(orderServiceUrl + "/api/v1/orders/my-orders?page=0&size=" + limit)
                .header("Authorization", bearerToken)
                .retrieve()
                .body(Map.class);
    }
}
