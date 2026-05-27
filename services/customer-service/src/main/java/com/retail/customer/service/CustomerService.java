package com.retail.customer.service;

import com.retail.customer.entity.Customer;
import com.retail.customer.exception.CustomerNotFoundException;
import com.retail.customer.repository.CustomerRepository;
import com.retail.customer.request.CustomerRequest;
import com.retail.customer.response.CustomerResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
@RequiredArgsConstructor
public class CustomerService {

    private final CustomerRepository customerRepository;

    public CustomerResponse getById(Integer id) {
        return customerRepository.findById(id)
                .map(this::toResponse)
                .orElseThrow(() -> new CustomerNotFoundException(id));
    }

    public CustomerResponse getByEmail(String email) {
        return customerRepository.findByEmailIgnoreCase(email)
                .map(this::toResponse)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Customer not found"));
    }

    public List<CustomerResponse> getAll() {
        return customerRepository.findAll().stream().map(this::toResponse).toList();
    }

    public Page<CustomerResponse> getPaged(int page, int size) {
        return customerRepository.findAll(PageRequest.of(page, size)).map(this::toResponse);
    }

    public CustomerResponse update(Integer id, CustomerRequest request) {
        Customer customer = customerRepository.findById(id)
                .orElseThrow(() -> new CustomerNotFoundException(id));
        customer.setFirstname(request.firstname());
        customer.setLastname(request.lastname());
        customer.setEmail(request.email());
        customer.setAddress(request.address());
        return toResponse(customerRepository.save(customer));
    }

    public CustomerResponse updateProfile(String email, CustomerRequest request) {
        Customer customer = customerRepository.findByEmail(email)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Customer not found"));
        customer.setFirstname(request.firstname());
        customer.setLastname(request.lastname());
        customer.setAddress(request.address());
        return toResponse(customerRepository.save(customer));
    }

    public void delete(Integer id) {
        if (!customerRepository.existsById(id)) {
            throw new CustomerNotFoundException(id);
        }
        customerRepository.deleteById(id);
    }

    private CustomerResponse toResponse(Customer c) {
        return new CustomerResponse(c.getId(), c.getFirstname(), c.getLastname(),
                c.getEmail(), c.getAddress(), c.getRole());
    }
}
