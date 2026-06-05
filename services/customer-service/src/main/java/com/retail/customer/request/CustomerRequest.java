package com.retail.customer.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record CustomerRequest(
        @NotBlank String firstname,
        @NotBlank String lastname,
        @NotBlank @Email String email,
        String address
) {}
