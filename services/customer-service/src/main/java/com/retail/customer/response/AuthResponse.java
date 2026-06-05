package com.retail.customer.response;

public record AuthResponse(
        String accessToken,
        String refreshToken
) {}
