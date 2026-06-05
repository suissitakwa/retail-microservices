package com.retail.product.service;

import com.retail.product.entity.Inventory;
import com.retail.product.entity.Product;
import com.retail.product.exception.ResourceNotFoundException;
import com.retail.product.repository.CategoryRepository;
import com.retail.product.repository.ProductRepository;
import com.retail.product.request.ProductRequest;
import com.retail.product.response.CategoryResponse;
import com.retail.product.response.ProductResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.cache.annotation.Caching;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ProductService {

    private final ProductRepository productRepository;
    private final CategoryRepository categoryRepository;

    @Cacheable(cacheNames = "productsList", key = "'all'", sync = true)
    public List<ProductResponse> getAll() {
        return productRepository.findAll().stream().map(this::toResponse).toList();
    }

    @Cacheable(cacheNames = "productById", key = "#id", sync = true)
    public ProductResponse getById(Integer id) {
        return toResponse(find(id));
    }

    public List<ProductResponse> getByCategory(Integer categoryId) {
        return productRepository.findByCategoryId(categoryId).stream().map(this::toResponse).toList();
    }

    @CacheEvict(cacheNames = "productsList", allEntries = true)
    public ProductResponse create(ProductRequest request) {
        var category = categoryRepository.findById(request.categoryId())
                .orElseThrow(() -> new ResourceNotFoundException("Category not found: " + request.categoryId()));

        Product product = Product.builder()
                .name(request.name())
                .description(request.description())
                .imageUrl(request.imageUrl())
                .price(request.price())
                .category(category)
                .build();

        // Default stock = 50 on creation
        Inventory inv = new Inventory();
        inv.setQuantity(50);
        inv.setProduct(product);
        product.setInventory(inv);

        return toResponse(productRepository.save(product));
    }

    @Caching(evict = {
            @CacheEvict(cacheNames = "productById", key = "#id"),
            @CacheEvict(cacheNames = "productsList", allEntries = true)
    })
    public ProductResponse update(Integer id, ProductRequest request) {
        Product product = find(id);
        var category = categoryRepository.findById(request.categoryId())
                .orElseThrow(() -> new ResourceNotFoundException("Category not found: " + request.categoryId()));

        product.setName(request.name());
        product.setDescription(request.description());
        product.setImageUrl(request.imageUrl());
        product.setPrice(request.price());
        product.setCategory(category);

        return toResponse(productRepository.save(product));
    }

    @Caching(evict = {
            @CacheEvict(cacheNames = "productById", key = "#id"),
            @CacheEvict(cacheNames = "productsList", allEntries = true)
    })
    public void delete(Integer id) {
        productRepository.deleteById(id);
    }

    private Product find(Integer id) {
        return productRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Product not found: " + id));
    }

    public ProductResponse toResponse(Product p) {
        Integer stock = (p.getInventory() != null) ? p.getInventory().getQuantity() : null;
        CategoryResponse cat = (p.getCategory() != null)
                ? new CategoryResponse(p.getCategory().getId(), p.getCategory().getName(), p.getCategory().getDescription())
                : null;
        return new ProductResponse(p.getId(), p.getName(), p.getDescription(),
                p.getImageUrl(), p.getPrice(), cat, stock);
    }
}
