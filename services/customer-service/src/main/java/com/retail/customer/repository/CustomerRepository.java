package com.retail.customer.repository;

import com.retail.customer.entity.Customer;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CustomerRepository extends JpaRepository<Customer, Integer> {
    Optional<Customer> findByEmail(String email);
    Optional<Customer> findByEmailIgnoreCase(String email);
    Optional<Customer> findByResetToken(String token);
    boolean existsByEmail(String email);
}
