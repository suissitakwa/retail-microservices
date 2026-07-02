package com.retail.order.repository;

import com.retail.order.entity.Order;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;

import java.util.Optional;

public interface OrderRepository extends JpaRepository<Order, Integer> {
    Page<Order> findByCustomerId(Integer customerId, Pageable pageable);
    Optional<Order> findByStripeSessionId(String sessionId);
    Optional<Order> findByStripePaymentIntentId(String paymentIntentId);

    // Two Stripe webhooks (checkout.session.completed, payment_intent.succeeded) can arrive
    // out of order or nearly simultaneously — pessimistic lock prevents double-processing.
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT o FROM Order o WHERE o.stripePaymentIntentId = :paymentIntentId")
    Optional<Order> findByStripePaymentIntentIdForUpdate(String paymentIntentId);
}
