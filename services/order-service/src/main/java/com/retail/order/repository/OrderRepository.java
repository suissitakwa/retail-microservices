package com.retail.order.repository;

import com.retail.order.entity.Order;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface OrderRepository extends JpaRepository<Order, Integer> {
    Page<Order> findByCustomerId(Integer customerId, Pageable pageable);
    Optional<Order> findByStripeSessionId(String sessionId);
    Optional<Order> findByStripePaymentIntentId(String paymentIntentId);
}
