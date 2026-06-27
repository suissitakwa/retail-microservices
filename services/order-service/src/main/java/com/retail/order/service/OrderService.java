package com.retail.order.service;

import com.retail.order.entity.Cart;
import com.retail.order.entity.Order;
import com.retail.order.entity.OrderItem;
import com.retail.order.enums.OrderStatus;
import com.retail.order.enums.PaymentMethod;
import com.retail.order.exception.ResourceNotFoundException;
import com.retail.order.kafka.OrderEvent;
import com.retail.order.kafka.OrderEventItem;
import com.retail.order.kafka.OrderProducer;
import com.retail.order.repository.CartRepository;
import com.retail.order.repository.OrderRepository;
import com.retail.order.response.CheckoutResponse;
import com.retail.order.response.OrderItemResponse;
import com.retail.order.response.OrderResponse;
import com.stripe.Stripe;
import com.stripe.model.checkout.Session;
import com.stripe.param.checkout.SessionCreateParams;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class OrderService {

    private final OrderRepository orderRepository;
    private final CartRepository  cartRepository;
    private final CartService     cartService;
    private final OrderProducer   orderProducer;

    @Value("${stripe.secret-key}")
    private String stripeSecretKey;

    @Value("${app.frontend.base-url:http://localhost:3000}")
    private String frontendBaseUrl;

    // ── Checkout ────────────────────────────────────────────────────────────

    @Transactional
    public CheckoutResponse checkout(Integer customerId, String customerEmail) throws Exception {
        Cart cart = cartService.findCart(customerId);

        if (cart.getItems().isEmpty()) {
            throw new IllegalStateException("Cannot checkout an empty cart");
        }

        // Build order
        Order order = Order.builder()
                .customerId(customerId)
                .reference("ORD-" + System.currentTimeMillis())
                .status(OrderStatus.PENDING)
                .paymentMethod(PaymentMethod.STRIPE)
                .build();

        BigDecimal total = BigDecimal.ZERO;
        for (var item : cart.getItems()) {
            OrderItem oi = OrderItem.builder()
                    .order(order).productId(item.getProductId())
                    .productName(item.getProductName())
                    .price(item.getPrice()).quantity(item.getQuantity())
                    .build();
            order.getOrderItems().add(oi);
            total = total.add(item.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
        }
        order.setTotalAmount(total);
        Order saved = orderRepository.save(order);

        // Clear cart
        cart.getItems().clear();
        cartRepository.save(cart);

        // Create Stripe session
        Stripe.apiKey = stripeSecretKey;
        SessionCreateParams params = SessionCreateParams.builder()
                .setMode(SessionCreateParams.Mode.PAYMENT)
                .setSuccessUrl(frontendBaseUrl + "/success?orderId=" + saved.getId())
                .setCancelUrl(frontendBaseUrl + "/cancel")
                .setPaymentIntentData(SessionCreateParams.PaymentIntentData.builder()
                        .putMetadata("orderId", saved.getId().toString()).build())
                .addLineItem(SessionCreateParams.LineItem.builder()
                        .setQuantity(1L)
                        .setPriceData(SessionCreateParams.LineItem.PriceData.builder()
                                .setCurrency("usd")
                                .setUnitAmount(total.multiply(BigDecimal.valueOf(100)).longValue())
                                .setProductData(SessionCreateParams.LineItem.PriceData.ProductData.builder()
                                        .setName("Order #" + saved.getId()).build())
                                .build())
                        .build())
                .build();
        Session session = Session.create(params);

        saved.setStripeSessionId(session.getId());
        orderRepository.save(saved);

        // Publish order.created Kafka event
        List<OrderEventItem> eventItems = saved.getOrderItems().stream()
                .map(oi -> new OrderEventItem(oi.getProductId(), oi.getQuantity()))
                .toList();
        orderProducer.sendOrderCreatedEvent(new OrderEvent(
                saved.getId(), customerId, customerEmail, total, eventItems));

        log.info("Checkout complete: orderId={} stripeSession={}", saved.getId(), session.getId());
        return new CheckoutResponse(session.getUrl(), saved.getId());
    }

    // ── Queries ──────────────────────────────────────────────────────────────

    public Page<OrderResponse> getMyOrders(Integer customerId, Pageable pageable) {
        return orderRepository.findByCustomerId(customerId, pageable).map(this::toResponse);
    }

    public OrderResponse getOrderDetail(Integer orderId, Integer customerId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
        if (!order.getCustomerId().equals(customerId)) {
            throw new SecurityException("Unauthorized: not your order");
        }
        return toResponse(order);
    }

    public List<OrderResponse> getAllOrders() {
        return orderRepository.findAll().stream().map(this::toResponse).toList();
    }

    @Transactional
    public void updateStatus(Integer orderId, OrderStatus newStatus) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
        order.setStatus(newStatus);
        orderRepository.save(order);
    }

    @Transactional
    public void cancel(Integer orderId, Integer customerId) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found: " + orderId));
        if (!order.getCustomerId().equals(customerId)) throw new SecurityException("Unauthorized");
        if (order.getStatus() != OrderStatus.PENDING) throw new IllegalStateException("Only PENDING orders can be cancelled");
        order.setStatus(OrderStatus.CANCELLED);
        orderRepository.save(order);
    }

    // ── Stripe webhook helpers ────────────────────────────────────────────────

    @Transactional
    public void attachPaymentIntent(String sessionId, String paymentIntentId) {
        orderRepository.findByStripeSessionId(sessionId).ifPresent(order -> {
            order.setStripePaymentIntentId(paymentIntentId);
            orderRepository.save(order);
        });
    }

    @Transactional
    public void markCompleted(String paymentIntentId) {
        orderRepository.findByStripePaymentIntentId(paymentIntentId).ifPresent(order -> {
            order.setStatus(OrderStatus.COMPLETED);
            orderRepository.save(order);
            log.info("Order {} marked COMPLETED via paymentIntent={}", order.getId(), paymentIntentId);
        });
    }

    // ── Mapper ───────────────────────────────────────────────────────────────

    private OrderResponse toResponse(Order o) {
        List<OrderItemResponse> items = o.getOrderItems().stream()
                .map(i -> new OrderItemResponse(i.getId(), i.getProductId(), i.getProductName(), i.getQuantity(), i.getPrice()))
                .toList();
        return new OrderResponse(o.getId(), o.getReference(), o.getCustomerId(),
                o.getTotalAmount(), o.getStatus(), o.getStripeSessionId(), items, o.getCreatedDate());
    }
}
