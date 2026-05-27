package com.retail.payment.repository;

import com.retail.payment.entity.Payment;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface PaymentRepository extends JpaRepository<Payment, Integer> {
    Optional<Payment> findByOrderId(Integer orderId);
    Optional<Payment> findByStripeSessionId(String stripeSessionId);
    Optional<Payment> findByStripePaymentIntentId(String stripePaymentIntentId);
}
