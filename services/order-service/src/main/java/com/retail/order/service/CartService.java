package com.retail.order.service;

import com.retail.order.entity.Cart;
import com.retail.order.entity.CartItem;
import com.retail.order.exception.ResourceNotFoundException;
import com.retail.order.repository.CartRepository;
import com.retail.order.request.AddToCartRequest;
import com.retail.order.response.CartItemResponse;
import com.retail.order.response.CartResponse;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class CartService {

    private final CartRepository cartRepository;
    private final ProductClient  productClient;

    public CartResponse getOrCreate(Integer customerId) {
        Cart cart = cartRepository.findByCustomerId(customerId)
                .orElseGet(() -> cartRepository.save(
                        Cart.builder().customerId(customerId).createdAt(LocalDateTime.now()).items(new java.util.ArrayList<>()).build()
                ));
        return toResponse(cart);
    }

    @Transactional
    public CartResponse addItem(Integer customerId, AddToCartRequest request) {
        Cart cart = cartRepository.findByCustomerId(customerId)
                .orElseGet(() -> cartRepository.save(
                        Cart.builder().customerId(customerId).createdAt(LocalDateTime.now()).items(new java.util.ArrayList<>()).build()
                ));

        // Fetch product name + price from product-service
        Map<String, Object> product = productClient.getProduct(request.productId());
        String productName = (String) product.get("name");
        BigDecimal price   = new BigDecimal(product.get("price").toString());

        cart.getItems().stream()
                .filter(i -> i.getProductId().equals(request.productId()))
                .findFirst()
                .ifPresentOrElse(
                        existing -> existing.setQuantity(existing.getQuantity() + request.quantity()),
                        () -> cart.getItems().add(CartItem.builder()
                                .cart(cart).productId(request.productId())
                                .productName(productName).price(price)
                                .quantity(request.quantity()).build())
                );

        return toResponse(cartRepository.save(cart));
    }

    @Transactional
    public CartResponse removeItem(Integer customerId, Integer productId) {
        Cart cart = findCart(customerId);
        cart.getItems().removeIf(i -> i.getProductId().equals(productId));
        return toResponse(cartRepository.save(cart));
    }

    @Transactional
    public void clear(Integer customerId) {
        Cart cart = findCart(customerId);
        cart.getItems().clear();
        cartRepository.save(cart);
    }

    Cart findCart(Integer customerId) {
        return cartRepository.findByCustomerId(customerId)
                .orElseThrow(() -> new ResourceNotFoundException("Cart not found for customer: " + customerId));
    }

    private CartResponse toResponse(Cart cart) {
        var items = cart.getItems().stream()
                .map(i -> new CartItemResponse(i.getId(), i.getProductId(), i.getProductName(), i.getPrice(), i.getQuantity()))
                .toList();
        BigDecimal total = items.stream()
                .map(i -> i.price().multiply(BigDecimal.valueOf(i.quantity())))
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        return new CartResponse(cart.getId(), cart.getCustomerId(), items, total);
    }
}
