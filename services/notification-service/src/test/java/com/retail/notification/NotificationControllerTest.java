package com.retail.notification;

import com.retail.notification.controller.NotificationController;
import com.retail.notification.response.NotificationResponse;
import com.retail.notification.service.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class NotificationControllerTest {

    @Mock NotificationService notificationService;

    NotificationController controller;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        controller = new NotificationController(notificationService);
    }

    // ── helpers ───────────────────────────────────────────────────────────────

    private static Authentication customerAuth(Integer customerId) {
        var auth = new UsernamePasswordAuthenticationToken("user@test.com", null, List.of());
        auth.setDetails(customerId);
        return auth;
    }

    private static NotificationResponse sample() {
        return new NotificationResponse(1, "ORDER_PLACED", "Your order has been placed",
                false, 10, "REF-001", LocalDateTime.now());
    }

    // ── GET /my ────────────────────────────────────────────────────────────────

    @Test
    void getMyNotifications_returnsListForCustomer() {
        when(notificationService.getMyNotifications(42)).thenReturn(List.of(sample()));

        List<NotificationResponse> result = controller.getMyNotifications(customerAuth(42));

        assertThat(result).hasSize(1);
        assertThat(result.get(0).type()).isEqualTo("ORDER_PLACED");
        assertThat(result.get(0).orderId()).isEqualTo(10);
        assertThat(result.get(0).orderReference()).isEqualTo("REF-001");
    }

    @Test
    void getMyNotifications_returnsEmptyList_whenNone() {
        when(notificationService.getMyNotifications(42)).thenReturn(List.of());

        assertThat(controller.getMyNotifications(customerAuth(42))).isEmpty();
    }

    // ── GET /unread-count ─────────────────────────────────────────────────────

    @Test
    void getUnreadCount_returnsCount() {
        when(notificationService.getUnreadCount(42)).thenReturn(3L);

        ResponseEntity<Map<String, Long>> response = controller.getUnreadCount(customerAuth(42));

        assertThat(response.getStatusCode().value()).isEqualTo(200);
        assertThat(response.getBody()).containsEntry("count", 3L);
    }

    @Test
    void getUnreadCount_returnsZero_whenAllRead() {
        when(notificationService.getUnreadCount(42)).thenReturn(0L);

        assertThat(controller.getUnreadCount(customerAuth(42)).getBody())
                .containsEntry("count", 0L);
    }

    // ── PATCH /{id}/read ──────────────────────────────────────────────────────

    @Test
    void markAsRead_returns200_andDelegates() {
        doNothing().when(notificationService).markAsRead(1, 42);

        ResponseEntity<Void> response = controller.markAsRead(1, customerAuth(42));

        assertThat(response.getStatusCode().value()).isEqualTo(200);
        verify(notificationService).markAsRead(1, 42);
    }
}
