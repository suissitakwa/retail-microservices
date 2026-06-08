package com.retail.notification;

import com.retail.notification.entity.Notification;
import com.retail.notification.repository.NotificationRepository;
import com.retail.notification.response.NotificationResponse;
import com.retail.notification.service.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class NotificationServiceTest {

    @Mock NotificationRepository notificationRepository;

    NotificationService service;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new NotificationService(notificationRepository);
    }

    // ── getMyNotifications ────────────────────────────────────────────────────

    @Test
    void getMyNotifications_returnsMappedResponsesOrderedByDate() {
        var n1 = Notification.builder()
                .id(1).type("ORDER_PLACED").message("Order placed").isRead(false)
                .customerId(42).orderId(10).orderReference("REF-001")
                .createdDate(LocalDateTime.now()).build();
        var n2 = Notification.builder()
                .id(2).type("PAYMENT_PAID").message("Payment received").isRead(true)
                .customerId(42).orderId(10).orderReference("REF-001")
                .createdDate(LocalDateTime.now().minusHours(1)).build();

        when(notificationRepository.findByCustomerIdOrderByCreatedDateDesc(42))
                .thenReturn(List.of(n1, n2));

        List<NotificationResponse> result = service.getMyNotifications(42);

        assertThat(result).hasSize(2);
        assertThat(result.get(0).type()).isEqualTo("ORDER_PLACED");
        assertThat(result.get(0).isRead()).isFalse();
        assertThat(result.get(1).type()).isEqualTo("PAYMENT_PAID");
        assertThat(result.get(1).isRead()).isTrue();
    }

    @Test
    void getMyNotifications_returnsEmptyList_whenNoneExist() {
        when(notificationRepository.findByCustomerIdOrderByCreatedDateDesc(42))
                .thenReturn(List.of());

        assertThat(service.getMyNotifications(42)).isEmpty();
    }

    // ── getUnreadCount ────────────────────────────────────────────────────────

    @Test
    void getUnreadCount_delegatesToRepository() {
        when(notificationRepository.countByCustomerIdAndIsReadFalse(42)).thenReturn(5L);

        assertThat(service.getUnreadCount(42)).isEqualTo(5L);
    }

    // ── markAsRead ────────────────────────────────────────────────────────────

    @Test
    void markAsRead_setsReadFlagAndSaves_whenOwner() {
        var notification = Notification.builder()
                .id(1).customerId(42).isRead(false).build();
        when(notificationRepository.findById(1)).thenReturn(Optional.of(notification));

        service.markAsRead(1, 42);

        assertThat(notification.isRead()).isTrue();
        verify(notificationRepository).save(notification);
    }

    @Test
    void markAsRead_throwsForbidden_whenWrongCustomer() {
        var notification = Notification.builder()
                .id(1).customerId(99).isRead(false).build();
        when(notificationRepository.findById(1)).thenReturn(Optional.of(notification));

        assertThatThrownBy(() -> service.markAsRead(1, 42))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("Unauthorized");
    }

    @Test
    void markAsRead_throwsNotFound_whenNotificationMissing() {
        when(notificationRepository.findById(99)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.markAsRead(99, 42))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("Notification not found");
    }
}
