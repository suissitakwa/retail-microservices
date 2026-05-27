package com.retail.customer.response;

import com.retail.customer.enums.Role;

public record CustomerResponse(
        Integer id,
        String firstname,
        String lastname,
        String email,
        String address,
        Role role
) {}
