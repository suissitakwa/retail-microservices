package com.retail.notification.client;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@Slf4j
public class CustomerClient {

    private final RestClient restClient;

    public CustomerClient(@Value("${services.customer-url:http://localhost:8083}") String customerUrl) {
        this.restClient = RestClient.builder().baseUrl(customerUrl).build();
    }

    public CustomerInfo getCustomerById(Integer customerId) {
        try {
            return restClient.get()
                    .uri("/internal/customers/{id}", customerId)
                    .retrieve()
                    .body(CustomerInfo.class);
        } catch (Exception e) {
            log.warn("Could not fetch customer {} from customer-service: {}", customerId, e.getMessage());
            return null;
        }
    }

    public record CustomerInfo(Integer id, String firstname, String lastname, String email) {}
}
