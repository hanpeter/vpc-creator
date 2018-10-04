# -*- coding: utf-8 -*-

from __future__ import absolute_import
import boto3


class Creator(object):

    def __init__(self):
        super().__init__()
        self._ec2 = boto3.client('ec2')
        self._cloudwatch = boto3.client('cloudwatch')

    def _create_vpc(self, name, cidr, creator):
        vpc = self._ec2.create_vpc(
            CidrBlock=cidr,
        ).get('Vpc', None)
        self._ec2.create_tags(
            Resources=[vpc.get('VpcId')],
            Tags=[
                {'Key': 'Name', 'Value': name},
                {'Key': 'Creator', 'Value': creator},
            ]
        )
        return vpc

    def _create_internet_gateway(self, vpc, name):
        igw = self._ec2.create_internet_gateway().get('InternetGateway')
        self._ec2.attach_internet_gateway(
            InternetGatewayId=igw.get('InternetGatewayId'),
            VpcId=vpc.get('VpcId'),
        )
        self._ec2.create_tags(
            Resources=[igw.get('InternetGatewayId')],
            Tags=[
                {'Key': 'Name', 'Value': name},
            ]
        )

    def _create_s3_endpoint(self, vpc):
        self._ec2.modify_vpc_attribute(
            EnableDnsHostnames={'Value': True},
            VpcId=vpc.get('VpcId'),
        )
        s3 = self._ec2.create_vpc_endpoint(
            ServiceName='com.amazonaws.us-east-1.s3',
            VpcId=vpc.get('VpcId'),
        ).get('VpcEndpoint')
        return s3

    def _create_subnet(self, vpc, az, cidr):
        subnet = self._ec2.create_subnet(
            AvailabilityZone=az,
            CidrBlock=cidr,
            VpcId=vpc.get('VpcId'),
        ).get('Subnet')
        self._ec2.create_tags(
            Resources=[subnet.get('SubnetId')],
            Tags=[
                {'Key': 'Name', 'Value': az},
            ]
        )
        return subnet

    def _create_nat_gateway(self, subnet, sns):
        eip = self._ec2.allocate_address(
            Domain='vpc',
        )
        nat = self._ec2.create_nat_gateway(
            AllocationId=eip.get('AllocationId'),
            SubnetId=subnet.get('SubnetId'),
        ).get('NatGateway')
        self._ec2.create_tags(
            Resources=[nat.get('NatGatewayId')],
            Tags=[
                {'Key': 'Name', 'Value': subnet.get('AvailabilityZone')},
            ]
        )
        self._ec2.get_waiter('nat_gateway_available').wait(
            NatGatewayIds=[nat.get('NatGatewayId')],
        )
        if sns:
            self._create_alarm(nat=nat, az=subnet.get('AvailabilityZone'), metric='BytesOutToDestination', sns=sns)
            self._create_alarm(nat=nat, az=subnet.get('AvailabilityZone'), metric='BytesOutToSource', sns=sns)
        return nat

    def _create_alarm(self, nat, az, metric, sns):
        self._cloudwatch.put_metric_alarm(
            AlarmName="awsnatgateway-{az}-{metric}".format(
                az=az, metric=metric,
            ),
            AlarmActions=[sns],
            MetricName=metric,
            Namespace='AWS/NATGateway',
            Statistic='Sum',
            Dimensions=[{
                'Name': 'NatGatewayId',
                'Value': nat.get('NatGatewayId')
            }],
            Period=300,
            EvaluationPeriods=3,
            Threshold=(5 << 30),  # 5 GB
            ComparisonOperator='GreaterThanOrEqualToThreshold',
        )

    def _create_route_table(self, vpc, subnet, nat, s3_endpoint):
        route_table = self._ec2.create_route_table(
            VpcId=vpc.get('VpcId'),
        ).get('RouteTable')
        self._ec2.associate_route_table(
            RouteTableId=route_table.get('RouteTableId'),
            SubnetId=subnet.get('SubnetId'),
        )
        self._ec2.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=nat.get('NatGatewayId'),
            RouteTableId=route_table.get('RouteTableId'),
        )
        self._ec2.modify_vpc_endpoint(
            VpcEndpointId=s3_endpoint.get('VpcEndpointId'),
            AddRouteTableIds=[route_table.get('RouteTableId')],
        )
        self._ec2.create_tags(
            Resources=[route_table.get('RouteTableId')],
            Tags=[
                {'Key': 'Name', 'Value': subnet.get('AvailabilityZone')},
            ]
        )
        return route_table

    def run(self, name, cidr, subnets, creator, sns):
        vpc = self._create_vpc(name=name, cidr=cidr, creator=creator)
        self._create_internet_gateway(vpc=vpc, name=name)
        s3_endpoint = self._create_s3_endpoint(vpc=vpc)

        for az, subnet_cidr in subnets.items():
            subnet = self._create_subnet(vpc=vpc, az=az, cidr=subnet_cidr)
            nat = self._create_nat_gateway(subnet=subnet, sns=sns)
            self._create_route_table(vpc=vpc, subnet=subnet, nat=nat, s3_endpoint=s3_endpoint)
