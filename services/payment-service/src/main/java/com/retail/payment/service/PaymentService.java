package com.retail.payment.service;

import com.retail.payment.entity.Payment;
import com.retail.payment.enums.PaymentStatus;
import com.retail.payment.kafka.PaymentNotificationRequest;
import com.retail.payment.kafka.PaymentProducer;
import com.retail.payment.repository.PaymentRepository;
import com.retail.payment.request.PaymentRequest;
import com.retail.payment.response.PaymentResponse;
import jakarta.persistence.EntityNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Slf4j
public class PaymentService {

    private final PaymentRepository paymentRepository;
    private final PaymentProducer paymentProducer;

    @Transactional
    public PaymentResponse createPayment(PaymentRequest request) {
        Payment payment = Payment.builder()
                .orderId(request.orderId())
                .customerId(request.customerId())
                .amount(request.amount())
                .currency(request.currency() != null ? request.currency() : "USD")
                .orderReference(request.orderReference())
                .stripeSessionId(request.stripeSessionId())
                .status(PaymentStatus.PENDING)
                .build();

        paymentRepository.save(payment);
        log.info("Created PENDING payment id={} for orderId={}", payment.getId(), payment.getOrderId());
        return toResponse(payment);
    }

    public PaymentResponse getById(Integer id) {
        return toResponse(findById(id));
    }

    public PaymentResponse getByOrderId(Integer orderId) {
        Payment payment = paymentRepository.findByOrderId(orderId)
                .orElseThrow(() -> new EntityNotFoundException("Payment not found for orderId=" + orderId));
        return toResponse(payment);
    }

    @Transactional
    public PaymentResponse confirmPayment(Integer id, String stripePaymentIntentId) {
        Payment payment = findById(id);

        payment.setStatus(PaymentStatus.PAID);
        payment.setStripePaymentIntentId(stripePaymentIntentId);
        paymentRepository.save(payment);

        log.info("Payment id={} confirmed as PAID", id);

        // Publish Kafka event so the monolith can update the order and notify the customer
        paymentProducer.sendPaymentConfirmation(new PaymentNotificationRequest(
                payment.getOrderId(),
                payment.getCustomerId(),
                payment.getOrderReference(),
                payment.getAmount(),
                "STRIPE"
        ));

        return toResponse(payment);
    }

    @Transactional
    public PaymentResponse failPayment(Integer id) {
        Payment payment = findById(id);
        payment.setStatus(PaymentStatus.FAILED);
        paymentRepository.save(payment);
        log.info("Payment id={} marked as FAILED", id);
        return toResponse(payment);
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private Payment findById(Integer id) {
        return paymentRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Payment not found id=" + id));
    }

    private PaymentResponse toResponse(Payment p) {
        return new PaymentResponse(
                p.getId(),
                p.getOrderId(),
                p.getCustomerId(),
                p.getAmount(),
                p.getCurrency(),
                p.getStatus(),
                p.getOrderReference(),
                p.getStripeSessionId(),
                p.getStripePaymentIntentId(),
                p.getCreatedAt()
        );
    }
}
