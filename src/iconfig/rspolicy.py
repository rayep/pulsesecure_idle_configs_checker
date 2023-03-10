"""
Resource policies parser

:::Changelog:::
(*use 'CHG-X -> Applied' while searching)

[Feb 2022]
CHG-01 -> RS policy parser logic updated, max_length optimizations made.

[04/03/22 - 3:30 PM IST]
CHG-02 -> Added "role_value" args for resource_policy_w_parent, resource_policy. file-policies &
          network-connect-bandwidth-policy using "role" tag instead "roles".

"""
from collections import defaultdict
from csv import DictWriter
from ..api import ICSXMLParser, logger, LOGGER
from ..xpath.rspolicy import *


class ICSRSPolicy(ICSXMLParser):
    """Base class for Resource policy parsing"""

    def __init__(self, xml_file: str, idle_user_roles: set) -> None:
        self.log_object = ''
        self.web_policies_ = {}
        self.file_policies_ = {}
        self.sam_policies_ = {}
        self.termserv_policies_ = {}
        self.html5_policies_ = {}
        self.vpntunnel_policies_ = {}
        self.idle_user_roles = idle_user_roles
        self.policy_length = []
        super().__init__(xml_file)

    def rs_policies(self) -> None:
        """Pipeline method to execute all Resource policies"""
        self.web_policies()
        self.file_policies()
        self.sam_policies()
        self.termserv_policies()
        self.html5_policies()
        self.vpntunnel_policies()   

    def resource_policy_w_parent(
            self,
            rspolicy_path: str,
            role_value: str = "roles") -> set:
        """Parsing Resource access policy (PARENT-TYPE) - Selected & Excluded policies
        ("All Roles" will be ignored)"""

        #CHG-02 -> _element_findall_values args changed to role_value.
        return {self._element_find_value(policy, "name"): sorted(self._element_findall_values(policy, role_value))
                for policy in self._handle_iterfind(rspolicy_path)
                if (self._element_find_value(policy, "parent-type") == "none" and
                (self._element_find_value(policy, "apply") != "all"))
                }

    def resource_policy(
            self,
            rspolicy_path: str,
            role_value: str = "roles") -> set:
        """Parsing Resource access policy (NON-PARENT TYPE) - Selected & Excluded policies
        ("All Roles" will be ignored)"""

        #CHG-02 -> _element_findall_values args changed to role_value.
        return {self._element_find_value(policy, "name"): sorted(self._element_findall_values(policy, role_value))
                for policy in self._handle_iterfind(rspolicy_path)
                if (self._element_find_value(policy, "apply") != "all")
                }

    def web_policies(self) -> None:
        """Web Policies"""
        self.log_object = self.web_policies.__name__
        if self.check_tree(WEB_ROOT):
            logger.info(LOGGER[self.log_object]['success'])
            for elem in [
                WEB_ACL,
                WEB_SSO_BASIC_NTLM,
                WEB_SSO_POST,
                WEB_SSO_HEADERS,
                WEB_CACHING_ACL,
                WEB_JAVA_ACL,
                WEB_CODESIGNING_ACL,
                WEB_SELECTIVE_REWRITE,
                WEB_COMPRESS_ACL,
                WEB_LAUNCHJSAM,
                WEB_CLIENTAUTH]:
                self.web_policies_[elem] = self.resource_policy_w_parent(elem)

            for elem in [
                WEB_SAML_ACCESS,
                WEB_SAML_SSO,
                WEB_CUSTOM_HEADER,
                WEB_CROSS_DOMAIN_ACL,
                WEB_PROXY_POLICY,
                WEB_PROTOCOL,
                WEB_ENCODING,
                WEB_SAML_EXTERNAL
            ]:
                self.web_policies_[elem] = self.resource_policy(elem)
        else:
            self.web_policies_ = set()
            logger.warning(LOGGER[self.log_object]['fail'])

    def file_policies(self) -> None:
        """File Policies"""
        self.log_object = self.file_policies.__name__
        if self.check_tree(FILE_ROOT):
            logger.info(LOGGER[self.log_object]['success'])
            for elem in [
                FILE_WIN_ACL,
                FILE_WIN_COMPRESS_ACL,
                FILE_WIN_SSO_ACL,
            ]:
                # CHG-02 -> Applied
                self.file_policies_[elem] = self.resource_policy_w_parent(elem, role_value="role")
        else:
            self.file_policies_ = set()
            logger.warning(LOGGER[self.log_object]['fail'])

    def sam_policies(self) -> None:
        """SAM Policies"""
        self.log_object = self.sam_policies.__name__
        if self.check_tree(SAM_ROOT):
            logger.info(LOGGER[self.log_object]['success'])
            self.sam_policies_[
                SAM_ACL] = self.resource_policy_w_parent(SAM_ACL)
        else:
            self.sam_policies_ = set()
            logger.warning(LOGGER[self.log_object]['fail'])

    def termserv_policies(self) -> None:
        """Terminal Services Policies"""
        self.log_object = self.termserv_policies.__name__
        if self.check_tree(TERM_SERV_ROOT):
            logger.info(LOGGER[self.log_object]['success'])
            self.termserv_policies_[
                TERM_SERV_ACL] = self.resource_policy_w_parent(TERM_SERV_ACL)
        else:
            self.termserv_policies_ = set()
            logger.warning(LOGGER[self.log_object]['fail'])

    def html5_policies(self) -> None:
        """HTML5 Policies"""
        self.log_object = self.html5_policies.__name__
        if self.check_tree(HTML5_ROOT):
            logger.info(LOGGER[self.log_object]['success'])
            self.html5_policies_[
                HTML5_ACL] = self.resource_policy_w_parent(HTML5_ACL)
        else:
            self.html5_policies_ = set()
            logger.warning(LOGGER[self.log_object]['fail'])

    def vpntunnel_policies(self) -> None:
        """VPN tunnelling Policies"""

        #CHG-02 -> Applied.
        self.log_object = self.vpntunnel_policies.__name__
        if self.check_tree(NC_ROOT):
            logger.info(LOGGER[self.log_object]['success'])

            # NC_BWIDTH removed and added as separated as that's only policy with "role" tag.
            for elem in [
                NC_ACL,
                NC_CONNPROF,
                NC_STUNNEL,
                NC_NODE_CONNPROF
            ]:
                self.vpntunnel_policies_[
                    elem] = self.resource_policy(elem)
                self.vpntunnel_policies_[
                    NC_BWIDTH] = self.resource_policy(NC_BWIDTH, role_value="role")
        else:
            self.vpntunnel_policies_ = set()
            logger.warning(LOGGER[self.log_object]['fail'])

    def _policy_parser(self, resource_policy: dict) -> dict:
        """
        RS policy dependency finder.
        This will check if the idle roles are part of any RS policy dependency.
        After filtering, data will be sent to policy padding method for filling with null values.
        """

        #CHG-01 -> Applied.
        result_roles = {}
        for role in self.idle_user_roles:
            result_ = defaultdict(list)
            for policy_type in resource_policy:
                # If the policy data is empty.
                if len(resource_policy[policy_type]) == 0:
                    # Creating empty dict to maintain CSV header integrity.
                    _ = result_[policy_type]
                    # This is needed as the CSV headers are static.
                    # default dict will just fill the empty one with empty LIST.
                policy_count = 0
                for policy in resource_policy[policy_type]:
                    # if type has atleast one policy configured.
                    if {role, }.issubset(resource_policy[policy_type][policy]):
                        result_[policy_type].append(policy)
                        policy_count += 1
                        # creating a new ddict with the same type name and policy name as value.
                    else:
                        # check if there are policy added to the dd already.
                        # To create TOP keys with empty LIST (useful for CSV)
                        if result_[policy_type]:
                            pass # ignore if another policy from same type added already. :)
                self.policy_length.append(len(result_[policy_type]))

            result_roles.update({role: result_})
            # Result dict will have mapping for idle role and its data.
        return self._policy_padding(result_roles)
        # padding ops for the result roles.

    def _policy_padding(self, roles_rspolicies: dict) -> dict:
        """
        Getting the length of filtered RS policy and filling with NULL - Padding.
        Sorting the filtered RS policy.
        """

        #CHG-01 -> Applied.
        if max(self.policy_length): # policy length is the no. of rs policies found.
            for role in roles_rspolicies:
                for policy in roles_rspolicies[role]:
                    if len(roles_rspolicies[role][policy]) != max(self.policy_length):
                    # catching policies that are less than the max. bucket and fill it with null.
                        diff_len = max(self.policy_length) - \
                            len(roles_rspolicies[role][policy])
                        roles_rspolicies[role][policy] = sorted(roles_rspolicies[role][policy]) + \
                            ["" for i in range(diff_len)] # empty "" added.
                    else:
                        roles_rspolicies[role][policy] = sorted(roles_rspolicies[role][policy])

        return roles_rspolicies

    def _first_key(self, rs_policy: dict) -> str:
        """First key from level 1"""
        return list(rs_policy)[0] # for getting the first idle role.

    def _second_key(self, rs_policy: dict) -> str:
        """First key from level 2"""
        # for getting the first resource policy type mapped to first idle role.
        # types - ACL, SSO-POST, etc.
        return list(rs_policy[self._first_key(rs_policy)])[0]

    def _first_policy_length(self, rs_policy: dict) -> int:
        """Getting the length of first policy - after padding"""
        # for getting the first policy type data.
        # i.e., how many web ACL policies were found.
        # Since we have added NULL values to match the max policy size
        # All policy will give the same length :)
        # NOTE: This length will be (-1) as we have ROLE header in the CSV report.
        return len(rs_policy[self._first_key(rs_policy)][self._second_key(rs_policy)])

    def write_web_policies(
            self,
            filename: str) -> None:
        """Web policies write CSV file"""

        self.policy_length = []
        rs_policy = self._policy_parser(self.web_policies_)
        with open(filename, mode='w', encoding='utf-8', newline='') as file_handle:
            write_output = DictWriter(
                file_handle, dialect='excel', fieldnames=WEB_POLICIES_HEADERS)
            write_output.writeheader()
            for role in rs_policy:
                roles = [
                    role, ] + [" " for i in range(self._first_policy_length(rs_policy)-1)]
                policy = rs_policy[roles[0]]
                for item in range(self._first_policy_length(rs_policy)):
                    write_output.writerow({
                        WEB_POLICIES_HEADERS[0]: roles[item],
                        WEB_POLICIES_HEADERS[1]: policy[WEB_ACL][item],
                        WEB_POLICIES_HEADERS[2]: policy[WEB_SSO_BASIC_NTLM][item],
                        WEB_POLICIES_HEADERS[3]: policy[WEB_SSO_POST][item],
                        WEB_POLICIES_HEADERS[4]: policy[WEB_SSO_HEADERS][item],
                        WEB_POLICIES_HEADERS[5]: policy[WEB_CACHING_ACL][item],
                        WEB_POLICIES_HEADERS[6]: policy[WEB_JAVA_ACL][item],
                        WEB_POLICIES_HEADERS[7]: policy[WEB_CODESIGNING_ACL][item],
                        WEB_POLICIES_HEADERS[8]: policy[WEB_SELECTIVE_REWRITE][item],
                        WEB_POLICIES_HEADERS[9]: policy[WEB_COMPRESS_ACL][item],
                        WEB_POLICIES_HEADERS[10]: policy[WEB_LAUNCHJSAM][item],
                        WEB_POLICIES_HEADERS[11]: policy[WEB_CLIENTAUTH][item],
                        WEB_POLICIES_HEADERS[12]: policy[WEB_SAML_ACCESS][item],
                        WEB_POLICIES_HEADERS[13]: policy[WEB_SAML_SSO][item],
                        WEB_POLICIES_HEADERS[14]: policy[WEB_CUSTOM_HEADER][item],
                        WEB_POLICIES_HEADERS[15]: policy[WEB_CROSS_DOMAIN_ACL][item],
                        WEB_POLICIES_HEADERS[16]: policy[WEB_PROXY_POLICY][item],
                        WEB_POLICIES_HEADERS[17]: policy[WEB_PROTOCOL][item],
                        WEB_POLICIES_HEADERS[18]: policy[WEB_ENCODING][item],
                        WEB_POLICIES_HEADERS[19]: policy[WEB_SAML_EXTERNAL][item],
                    })

    def write_file_policies(self, filename: str) -> None:
        """Writing File policies to CSV"""

        self.policy_length = []
        rs_policy = self._policy_parser(self.file_policies_)
        with open(filename, mode='w', encoding='utf-8', newline='') as file_handle:
            write_output = DictWriter(
                file_handle, dialect='excel', fieldnames=FILE_POLICIES_HEADERS)
            write_output.writeheader()
            for role in rs_policy:
                roles = [
                    role, ] + [" " for i in range(self._first_policy_length(rs_policy)-1)]
                policy = rs_policy[roles[0]]
                for item in range(self._first_policy_length(rs_policy)):
                    write_output.writerow({
                        FILE_POLICIES_HEADERS[0]: roles[item],
                        FILE_POLICIES_HEADERS[1]: policy[FILE_WIN_ACL][item],
                        FILE_POLICIES_HEADERS[2]: policy[FILE_WIN_SSO_ACL][item],
                        FILE_POLICIES_HEADERS[3]: policy[FILE_WIN_COMPRESS_ACL][item]
                    })

    def write_sam_policies(self, filename: str) -> None:
        """Writing SAM policies to CSV"""

        self.policy_length = []
        rs_policy = self._policy_parser(self.sam_policies_)
        with open(filename, mode='w', encoding='utf-8', newline='') as file_handle:
            write_output = DictWriter(
                file_handle, dialect='excel', fieldnames=SAM_POLICIES_HEADERS)
            write_output.writeheader()
            for role in rs_policy:
                roles = [
                    role, ] + [" " for i in range(self._first_policy_length(rs_policy)-1)]
                policy = rs_policy[roles[0]]
                for item in range(self._first_policy_length(rs_policy)):
                    write_output.writerow({
                        SAM_POLICIES_HEADERS[0]: roles[item],
                        SAM_POLICIES_HEADERS[1]: policy[SAM_ACL][item]
                    })

    def write_termsrv_policies(self, filename: str) -> None:
        """Writing termserv policies to CSV"""

        self.policy_length = []
        rs_policy = self._policy_parser(self.termserv_policies_)
        with open(filename, mode='w', encoding='utf-8', newline='') as file_handle:
            write_output = DictWriter(
                file_handle, dialect='excel', fieldnames=TERMSERV_POLICIES_HEADERS)
            write_output.writeheader()
            for role in rs_policy:
                roles = [
                    role, ] + [" " for i in range(self._first_policy_length(rs_policy)-1)]
                policy = rs_policy[roles[0]]
                for item in range(self._first_policy_length(rs_policy)):
                    write_output.writerow({
                        TERMSERV_POLICIES_HEADERS[0]: roles[item],
                        TERMSERV_POLICIES_HEADERS[1]: policy[TERM_SERV_ACL][item]
                    })

    def write_html5_policies(self, filename: str) -> None:
        """Writing HTML5 policies to CSV"""

        self.policy_length = []
        rs_policy = self._policy_parser(self.html5_policies_)
        with open(filename, mode='w', encoding='utf-8', newline='') as file_handle:
            write_output = DictWriter(
                file_handle, dialect='excel', fieldnames=HTML5_POLICIES_HEADERS)
            write_output.writeheader()
            for role in rs_policy:
                roles = [
                    role, ] + [" " for i in range(self._first_policy_length(rs_policy)-1)]
                policy = rs_policy[roles[0]]
                for item in range(self._first_policy_length(rs_policy)):
                    write_output.writerow({
                        HTML5_POLICIES_HEADERS[0]: roles[item],
                        HTML5_POLICIES_HEADERS[1]: policy[HTML5_ACL][item]
                    })

    def write_vpntunnel_policies(self, filename: str) -> None:
        """Writing HTML5 policies to CSV"""

        self.policy_length = []
        rs_policy = self._policy_parser(self.vpntunnel_policies_)
        with open(filename, mode='w', encoding='utf-8', newline='') as file_handle:
            write_output = DictWriter(
                file_handle, dialect='excel', fieldnames=NC_POLICIES_HEADERS)
            write_output.writeheader()
            for role in rs_policy:
                roles = [
                    role, ] + [" " for i in range(self._first_policy_length(rs_policy)-1)]
                policy = rs_policy[roles[0]]
                for item in range(self._first_policy_length(rs_policy)):
                    write_output.writerow({
                        NC_POLICIES_HEADERS[0]: roles[item],
                        NC_POLICIES_HEADERS[1]: policy[NC_ACL][item],
                        NC_POLICIES_HEADERS[2]: policy[NC_CONNPROF][item],
                        NC_POLICIES_HEADERS[3]: policy[NC_STUNNEL][item],
                        NC_POLICIES_HEADERS[4]: policy[NC_BWIDTH][item],
                        NC_POLICIES_HEADERS[5]: policy[NC_NODE_CONNPROF][item]
                    })
