"""
校验对比器模块
"""
from typing import List, Dict
from src.models import (
    UserSubscription, IAMUser, ComparisonResult, 
    VerificationResult, GroupVerification
)
from src.logger import get_logger


class VerificationEngine:
    """校验对比器"""
    
    def __init__(self):
        self.logger = get_logger("verification_engine")
    
    def compare_users(self, csv_users: List[UserSubscription], iam_users: List[IAMUser]) -> ComparisonResult:
        """对比CSV用户与IAM用户"""
        csv_usernames = {user.get_username() for user in csv_users}
        iam_usernames = {user.username for user in iam_users}
        
        matched = csv_usernames & iam_usernames
        new_users = list(csv_usernames - iam_usernames)
        missing_users = list(iam_usernames - csv_usernames)
        
        # 检查需要更新的用户
        updated_users = []
        csv_user_dict = {user.get_username(): user for user in csv_users}
        iam_user_dict = {user.username: user for user in iam_users}
        
        for username in matched:
            csv_user = csv_user_dict[username]
            iam_user = iam_user_dict[username]
            
            # 检查邮箱是否需要更新
            if csv_user.email != iam_user.email:
                updated_users.append(username)
        
        return ComparisonResult(
            csv_users_count=len(csv_users),
            iam_users_count=len(iam_users),
            matched_count=len(matched),
            new_users=new_users,
            updated_users=updated_users,
            missing_users=missing_users
        )
    
    def verify_group_memberships(self, expected: Dict, actual: Dict) -> VerificationResult:
        """验证组成员关系"""
        group_verifications = {}
        total_consistent = 0
        
        for group_name in expected:
            expected_members = set(expected[group_name])
            actual_members = set(actual.get(group_name, []))
            
            missing = list(expected_members - actual_members)
            extra = list(actual_members - expected_members)
            is_consistent = len(missing) == 0 and len(extra) == 0
            
            if is_consistent:
                total_consistent += 1
            
            group_verifications[group_name] = GroupVerification(
                group_name=group_name,
                expected_members=list(expected_members),
                actual_members=list(actual_members),
                missing_members=missing,
                extra_members=extra,
                is_consistent=is_consistent
            )
        
        consistency_rate = total_consistent / len(expected) if expected else 1.0
        
        return VerificationResult(
            total_users=sum(len(members) for members in expected.values()),
            matched_users=total_consistent,
            mismatched_users=[],
            group_verification=group_verifications,
            consistency_rate=consistency_rate
        )