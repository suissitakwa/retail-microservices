package com.retail.order.entity;

import com.retail.order.enums.OrderStatus;
import com.retail.order.enums.PaymentMethod;
import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "retail_order")
@EntityListeners(AuditingEntityListener.class)
@Getter @Setter
@Builder @NoArgsConstructor @AllArgsConstructor
public class Order {

    @Id @GeneratedValue
    private Integer id;

    @Column(unique = true, nullable = false)
    private String reference;

    private Integer customerId;
    private BigDecimal totalAmount;
    private String stripeSessionId;
    private String stripePaymentIntentId;

    @Enumerated(EnumType.STRING)
    private PaymentMethod paymentMethod;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status = OrderStatus.PENDING;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderItem> orderItems = new ArrayList<>();

    @CreatedDate
    @Column(updatable = false, nullable = false)
    private LocalDateTime createdDate;

    @LastModifiedDate
    @Column(insertable = false)
    private LocalDateTime lastModifiedDate;
}
