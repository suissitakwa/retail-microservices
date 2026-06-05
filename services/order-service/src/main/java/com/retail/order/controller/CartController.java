package com.retail.order.controller;

import com.retail.order.request.AddToCartRequest;
import com.retail.order.response.CartResponse;
import com.retail.order.service.CartService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/cart")
@RequiredArgsConstructor
public class CartController {

    private final CartService cartService;

    @GetMapping
    public ResponseEntity<CartResponse> getCart(Authentication auth) {
        return ResponseEntity.ok(cartService.getOrCreate(customerId(auth)));
    }

    @PostMapping("/add")
    public ResponseEntity<CartResponse> addItem(Authentication auth,
                                                @Valid @RequestBody AddToCartRequest request) {
        return ResponseEntity.ok(cartService.addItem(customerId(auth), request));
    }

    @DeleteMapping("/remove/{productId}")
    public ResponseEntity<CartResponse> removeItem(Authentication auth,
                                                   @PathVariable Integer productId) {
        return ResponseEntity.ok(cartService.removeItem(customerId(auth), productId));
    }

    @DeleteMapping("/clear")
    public ResponseEntity<Void> clear(Authentication auth) {
        cartService.clear(customerId(auth));
        return ResponseEntity.noContent().build();
    }

    private Integer customerId(Authentication auth) {
        return (Integer) auth.getDetails();
    }
}
