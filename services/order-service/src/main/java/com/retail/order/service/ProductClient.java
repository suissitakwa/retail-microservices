package com.retail.order.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

/**
 * Thin HTTP client to product-service.
 * Uses RestClient (Spring 6) — no Feign dependency needed.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class ProductClient {

    private final RestClient restClient;

    @Value("${product-service.url:http://localhost:8084}")
    private String productServiceUrl;

    @SuppressWarnings("unchecked")
    public Map<String, Object> getProduct(Integer productId) {
        log.info("Fetching product {} from product-service", productId);
        return restClient.get()
                .uri(productServiceUrl + "/api/v1/products/" + productId)
                .retrieve()
                .body(Map.class);
    }
}
