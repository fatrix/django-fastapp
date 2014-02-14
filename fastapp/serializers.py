from rest_framework import serializers
from fastapp.models import Base, Apy, Setting

class ApySerializer(serializers.ModelSerializer):
    class Meta:
        model = Apy
        fields = ('id', 'name', 'module')

class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ('id', 'key', 'value')

class BaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Base
        fields = ('id', 'name', 'uuid')
    #apy = serializers.HyperlinkedRelatedField(many=True, view_name='apy-detail', read_only=True)
    apy = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

