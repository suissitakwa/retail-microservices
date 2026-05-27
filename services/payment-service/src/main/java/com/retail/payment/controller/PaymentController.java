package com.retail.payment.controller;

import com.retail.payment.request.PaymentRequest;
import com.retail.payment.response.PaymentResponse;
import com.retail.payment.service.PaymentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@RestController
@RequestMapping("/api/v1/payments")
@RequiredArgsConstructor
public class PaymentController {

    private final PaymentService paymentService;

    /** Called by the monolith after creating an order + Stripe session */
    @PostMapping
    public ResponseEntity<PaymentResponse> create(@Valid @RequestBody PaymentRequest request) {
        PaymentResponse response = paymentService.createPayment(request);
        return ResponseEntity
                .created(URI.create("/api/v1/payments/" + response.id()))
                .body(response);
    }

    @GetMapping("/{id}")
    public ResponseEntity<PaymentResponse> getById(@PathVariable Integer id) {
        return ResponseEntity.ok(paymentService.getById(id));
    }

    @GetMapping("/order/{orderId}")
    public ResponseEntity<PaymentResponse> getByOrderId(@PathVariable Integer orderId) {
        return ResponseEntity.ok(paymentService.getByOrderId(orderId));
    }

    /** Called by the monolith after Stripe payment_intent.succeeded webhook */
    @PatchMapping("/{id}/confirm")
    public ResponseEntity<PaymentResponse> confirm(
            @PathVariable Integer id,
            @RequestParam String stripePaymentIntentId
    ) {
        return ResponseEntity.ok(paymentService.confirmPayment(id, stripePaymentIntentId));
    }

    /** Called if payment fails or is cancelled */
    @PatchMapping("/{id}/fail")
    public ResponseEntity<PaymentResponse> fail(@PathVariable Integer id) {
        return ResponseEntity.ok(paymentService.failPayment(id));
    }
}
