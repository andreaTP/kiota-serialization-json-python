from __future__ import annotations

import base64
import json
import re
import warnings
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from dateutil import parser
from kiota_abstractions.serialization import (
    AdditionalDataHolder,
    Parsable,
    ParsableFactory,
    ParseNode,
)

T = TypeVar("T")

U = TypeVar("U", bound=Parsable)

K = TypeVar("K", bound=Enum)


class JsonParseNode(ParseNode, Generic[T, U]):

    on_before_assign_field_values: Optional[Callable[[Parsable], None]] = None
    on_after_assign_field_values: Optional[Callable[[Parsable], None]] = None

    def __init__(self, node: Any) -> None:
        """
        Args:
            node (Any):The JsonElement to initialize the node with
        """
        self._json_node = node

    def get_str_value(self) -> Optional[str]:
        """Gets the string value from the json node
        Returns:
            str: The string value of the node
        """
        if self._json_node or self._json_node == '':
            return str(self._json_node)
        return None

    def get_child_node(self, identifier: str) -> Optional[ParseNode]:
        """Gets a new parse node for the given identifier
        Args:
            identifier (str): The identifier of the current node property
        Returns:
            Optional[ParseNode]: A new parse node for the given identifier
        """
        if self._json_node and self._json_node.get(identifier):
            return JsonParseNode(self._json_node[identifier])
        return None

    def get_bool_value(self) -> Optional[bool]:
        """Gets the boolean value of the json node
        Returns:
            bool: The boolean value of the node
        """
        if self._json_node or self._json_node is False:
            return bool(self._json_node)
        return None

    def get_int_value(self) -> Optional[int]:
        """Gets the integer value of the json node
        Returns:
            int: The integer value of the node
        """
        if self._json_node:
            return int(self._json_node)
        return None

    def get_float_value(self) -> Optional[float]:
        """Gets the float value of the json node
        Returns:
            float: The integer value of the node
        """
        if self._json_node:
            return float(self._json_node)
        return None

    def get_uuid_value(self) -> Optional[UUID]:
        """Gets the UUID value of the json node
        Returns:
            UUID: The GUID value of the node
        """
        if self._json_node:
            return UUID(self._json_node)
        return None

    def get_datetime_value(self) -> Optional[datetime]:
        """Gets the datetime value of the json node
        Returns:
            datetime: The datetime value of the node
        """
        datetime_str = self.get_str_value()
        if datetime_str:
            datetime_obj = parser.parse(datetime_str)
            return datetime_obj
        return None

    def get_timedelta_value(self) -> Optional[timedelta]:
        """Gets the timedelta value of the node
        Returns:
            timedelta: The timedelta value of the node
        """
        datetime_str = self.get_str_value()
        if datetime_str:
            datetime_obj = parser.parse(datetime_str)
            return timedelta(
                hours=datetime_obj.hour, minutes=datetime_obj.minute, seconds=datetime_obj.second
            )
        return None

    def get_date_value(self) -> Optional[date]:
        """Gets the date value of the node
        Returns:
            date: The datevalue of the node in terms on year, month, and day.
        """
        datetime_str = self.get_str_value()
        if datetime_str:
            datetime_obj = parser.parse(datetime_str)
            return datetime_obj.date()
        return None

    def get_time_value(self) -> Optional[time]:
        """Gets the time value of the node
        Returns:
            time: The time value of the node in terms of hour, minute, and second.
        """
        datetime_str = self.get_str_value()
        if datetime_str:
            datetime_obj = parser.parse(datetime_str)
            return datetime_obj.time()
        return None

    def get_collection_of_primitive_values(self, primitive_type) -> Optional[List[T]]:
        """Gets the collection of primitive values of the node
        Returns:
            List[T]: The collection of primitive values
        """

        def func(item):
            generic_type = type(item)
            current_parse_node = JsonParseNode(item)
            if generic_type == bool:
                return current_parse_node.get_bool_value()
            if generic_type == str:
                return current_parse_node.get_str_value()
            if generic_type == int:
                return current_parse_node.get_int_value()
            if generic_type == float:
                return current_parse_node.get_float_value()
            if generic_type == UUID:
                return current_parse_node.get_uuid_value()
            if generic_type == datetime:
                return current_parse_node.get_datetime_value()
            if generic_type == timedelta:
                return current_parse_node.get_timedelta_value()
            if generic_type == date:
                return current_parse_node.get_time_value()
            if generic_type == time:
                return current_parse_node.get_time_value()
            raise Exception(f"Encountered an unknown type during deserialization {generic_type}")

        if isinstance(self._json_node, str):
            return list(map(func, json.loads(self._json_node)))
        return list(map(func, list(self._json_node)))

    def get_collection_of_object_values(self, factory: ParsableFactory) -> List[U]:
        """Gets the collection of type U values from the json node
        Returns:
            List[U]: The collection of model object values of the node
        """
        return list(
            map(
                lambda x: JsonParseNode(x).get_object_value(factory),  # type: ignore
                self._json_node
            )
        )

    def get_collection_of_enum_values(self, enum_class: K) -> List[Optional[K]]:
        """Gets the collection of enum values of the json node
        Returns:
            List[K]: The collection of enum values
        """
        raw_values = self.get_str_value()
        if not raw_values:
            return []

        return list(
            map(lambda x: JsonParseNode(x).get_enum_value(enum_class), raw_values.split(","))
        )

    def get_enum_value(self, enum_class: K) -> Optional[K]:
        """Gets the enum value of the node
        Returns:
            Optional[K]: The enum value of the node
        """
        raw_key = self.get_str_value()
        camel_case_key = None
        if raw_key:
            if raw_key.lower() == "none":
                # None is a reserved keyword in python
                camel_case_key = "None_"
            else:
                camel_case_key = raw_key[0].upper() + raw_key[1:]
        if camel_case_key:
            try:
                return enum_class[camel_case_key]  # type: ignore
            except KeyError:
                raise Exception(f'Invalid key: {camel_case_key} for enum {enum_class}.')
        return None

    def get_object_value(self, factory: ParsableFactory) -> U:
        """Gets the model object value of the node
        Returns:
            Parsable: The model object value of the node
        """
        result = factory.create_from_discriminator_value(self)
        if self.on_before_assign_field_values:
            self.on_before_assign_field_values(result)
        self._assign_field_values(result)
        if self.on_after_assign_field_values:
            self.on_after_assign_field_values(result)
        return result

    def get_bytes_value(self) -> Optional[bytes]:
        """Get a bytearray value from the nodes
        Returns:
            bytearray: The bytearray value from the nodes
        """
        base64_string = self.get_str_value()
        if not base64_string:
            return None
        return base64_string.encode("utf-8")

    def get_on_before_assign_field_values(self) -> Optional[Callable[[Parsable], None]]:
        """Gets the callback called before the node is deserialized.
        Returns:
            Callable[[Parsable], None]: the callback called before the node is deserialized.
        """
        return self.on_before_assign_field_values

    def get_on_after_assign_field_values(self) -> Optional[Callable[[Parsable], None]]:
        """Gets the callback called before the node is deserialized.
        Returns:
            Callable[[Parsable], None]: the callback called before the node is deserialized.
        """
        return self.on_after_assign_field_values

    def set_on_before_assign_field_values(self, value: Callable[[Parsable], None]) -> None:
        """Sets the callback called before the node is deserialized.
        Args:
            value (Callable[[Parsable], None]): the callback called before the node is
            deserialized.
        """
        self.on_before_assign_field_values = value

    def set_on_after_assign_field_values(self, value: Callable[[Parsable], None]) -> None:
        """Sets the callback called after the node is deserialized.
        Args:
            value (Callable[[Parsable], None]): the callback called after the node is
            deserialized.
        """
        self.on_after_assign_field_values = value

    def _assign_field_values(self, item: U) -> None:

        object_dict = self._json_node

        item_additional_data = None

        # if object is null
        if not object_dict:
            return

        if isinstance(item, AdditionalDataHolder):
            item_additional_data = item.additional_data

        field_deserializers = item.get_field_deserializers()

        for key, val in object_dict.items():
            deserializer = field_deserializers.get(key)
            if deserializer:
                deserializer(JsonParseNode(val))
            elif item_additional_data is not None:
                item_additional_data[key] = val
            else:
                warnings.warn(
                    f"Found additional property {key} to \
                    deserialize but the model doesn't support additional data"
                )
