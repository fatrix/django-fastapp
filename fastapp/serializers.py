from rest_framework import serializers
from fastapp.models import Base, Apy, Setting, Counter

class CounterSerializer(serializers.ModelSerializer):

    class Meta:
        model = Counter
        fields = ('executed', 'failed')

class ApySerializer(serializers.ModelSerializer):
    counter = CounterSerializer(many=False, read_only=True)

    class Meta:
        model = Apy
        fields = ('id', 'name', 'module', 'counter')
        #fields = ('id', 'name', 'module' )

    #def get_counter(self, obj):
    #    return obj.counter.executed

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

