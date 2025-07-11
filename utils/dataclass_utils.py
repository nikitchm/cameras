# dataclass_utils.py
from dataclasses import asdict, is_dataclass
from typing import Type, TypeVar, Any
import copy

# Define a TypeVar bound to a dataclass type for better type hinting
_T = TypeVar('_T') # Represents any type
_DataclassType = TypeVar('_DataclassType', bound=Any) # Represents a type that is a dataclass


def create_child_from_parent(
    child_dataclass_type: Type[_DataclassType], # The target Child dataclass type
    parent_obj: Any,                             # The source Parent object
    **child_kwargs: Any                          # Any additional child-specific fields
) -> _DataclassType:
    """
    Initializes a child dataclass instance using common fields from a parent object
    and additional child-specific keyword arguments.

    Args:
        child_dataclass_type: The dataclass type of the child (e.g., Child).
        parent_obj: An instance of the parent dataclass (or any object
                    that provides the common fields).
        **child_kwargs: Keyword arguments for the child's new/specific fields.

    Returns:
        An instance of child_dataclass_type.

    Raises:
        TypeError: If parent_obj is not a dataclass instance.

    Problems:
        unfortunately, create_child_from_parent relies on asdict() function, which converts the custom data class into a dictionary.
        The explicit argument assinment reverses this conversion. However, see create_child_from_parent_deep() which doesn't have that problem.

    Usage:
        # Create a child object using the utility function
        child_obj = create_child_from_parent(
            Child,                       # Pass the Child class itself
            parent_obj,
            new_field_1=45.67,
            new_field_2=False
        )
    """
    if not is_dataclass(parent_obj):
        raise TypeError(f"parent_obj must be a dataclass instance, got {type(parent_obj)}")

    parent_fields = asdict(parent_obj)

    # Filter to include only fields that the child dataclass also has and are init-able
    # We use child_dataclass_type.__dataclass_fields__ to check for fields defined
    # in the child type, including those inherited.
    common_init_args = {
        k: v for k, v in parent_fields.items()
        if k in child_dataclass_type.__dataclass_fields__
           and child_dataclass_type.__dataclass_fields__[k].init
    }

    # Combine with child-specific arguments, with child_kwargs overriding if names conflict
    all_init_args = {**common_init_args, **child_kwargs}

    return child_dataclass_type(**all_init_args)


# You could integrate deepcopy into the utility function as well
def create_child_from_parent_deep(
    child_dataclass_type: Type[_DataclassType],
    parent_obj: Any,
    **child_kwargs: Any
) -> _DataclassType:
    if not is_dataclass(parent_obj):
        raise TypeError(f"parent_obj must be a dataclass instance, got {type(parent_obj)}")

    # Deep copy the parent object's fields for initialization
    # This prevents the asdict issue and ensures independence
    parent_init_args = {}
    for field in parent_obj.__dataclass_fields__.values():
        if field.init:
            parent_init_args[field.name] = copy.deepcopy(getattr(parent_obj, field.name))

    # Add/override with child-specific kwargs
    all_init_args = {**parent_init_args, **child_kwargs}

    return child_dataclass_type(**all_init_args)