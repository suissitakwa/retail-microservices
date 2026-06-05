package com.retail.product.service;

import com.retail.product.entity.Category;
import com.retail.product.exception.ResourceNotFoundException;
import com.retail.product.repository.CategoryRepository;
import com.retail.product.request.CategoryRequest;
import com.retail.product.response.CategoryResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class CategoryService {

    private final CategoryRepository categoryRepository;

    public List<CategoryResponse> getAll() {
        return categoryRepository.findAll().stream().map(this::toResponse).toList();
    }

    public CategoryResponse getById(Integer id) {
        return toResponse(find(id));
    }

    public CategoryResponse create(CategoryRequest request) {
        Category cat = Category.builder().name(request.name()).description(request.description()).build();
        return toResponse(categoryRepository.save(cat));
    }

    public CategoryResponse update(Integer id, CategoryRequest request) {
        Category cat = find(id);
        cat.setName(request.name());
        cat.setDescription(request.description());
        return toResponse(categoryRepository.save(cat));
    }

    public void delete(Integer id) {
        categoryRepository.deleteById(id);
    }

    private Category find(Integer id) {
        return categoryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Category not found: " + id));
    }

    public CategoryResponse toResponse(Category c) {
        return new CategoryResponse(c.getId(), c.getName(), c.getDescription());
    }
}
