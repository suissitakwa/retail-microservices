package com.retail.order.controller;

import com.retail.order.enums.OrderStatus;
import com.retail.order.response.CheckoutResponse;
import com.retail.order.response.OrderResponse;
import com.retail.order.service.OrderService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    /** Create Stripe session + save order + publish Kafka event */
    @PostMapping("/checkout")
    public ResponseEntity<CheckoutResponse> checkout(Authentication auth) throws Exception {
        return ResponseEntity.ok(orderService.checkout(customerId(auth), auth.getName()));
    }

    @GetMapping("/my-orders")
    public Page<OrderResponse> myOrders(Authentication auth,
                                        @RequestParam(defaultValue = "0") int page,
                                        @RequestParam(defaultValue = "10") int size) {
        return orderService.getMyOrders(customerId(auth), PageRequest.of(page, size));
    }

    @GetMapping("/my-orders/{orderId}")
    public ResponseEntity<OrderResponse> orderDetail(Authentication auth,
                                                     @PathVariable Integer orderId) {
        return ResponseEntity.ok(orderService.getOrderDetail(orderId, customerId(auth)));
    }

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @GetMapping("/admin/orders")
    public List<OrderResponse> allOrders() {
        return orderService.getAllOrders();
    }

    @PreAuthorize("hasAuthority('ROLE_ADMIN')")
    @PatchMapping("/{orderId}/status")
    public ResponseEntity<Void> updateStatus(@PathVariable Integer orderId,
                                             @RequestParam OrderStatus status) {
        orderService.updateStatus(orderId, status);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{orderId}/cancel")
    public ResponseEntity<Void> cancel(Authentication auth, @PathVariable Integer orderId) {
        orderService.cancel(orderId, customerId(auth));
        return ResponseEntity.ok().build();
    }

    private Integer customerId(Authentication auth) {
        return (Integer) auth.getDetails();
    }
}
